from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional, Any
import requests

# ============ Odoo Configuration ============
ODOO_URL = "http://localhost:8069"
ODOO_DB = "odoo_ai"
ODOO_UID = 2
ODOO_PASSWORD = "odoo"

app = FastAPI(title="Odoo Product Service")

def call_odoo(model: str, method: str, args: List[Any]) -> Any:
    """Generic Odoo RPC call"""
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "service": "object",
            "method": "execute_kw",
            "args": [ODOO_DB, ODOO_UID, ODOO_PASSWORD, model, method, args]
        },
        "id": 1
    }
    
    response = requests.post(f"{ODOO_URL}/jsonrpc", json=payload)
    result = response.json()
    
    if "error" in result:
        raise Exception(f"{result['error']['data']['message']}")
    
    return result.get("result")

# ============ Request Models ============

class ProductCreateRequest(BaseModel):
    name: str
    list_price: Optional[float] = None
    standard_price: Optional[float] = None
    type: Optional[str] = None  # Let Odoo provide default
    categ_name: Optional[str] = None
    barcode: Optional[str] = None
    description: Optional[str] = None
    uom_name: Optional[str] = None
    taxes_names: Optional[List[str]] = None

class ProductFilterRequest(BaseModel):
    """Filters for searching products"""
    name: Optional[str] = None
    categ_id: Optional[int] = None
    limit: int = 10
    offset: int = 0
    fields: List[str] = ["id", "name", "list_price", "type", "categ_id", "barcode"]

class ProductResponse(BaseModel):
    success: bool
    product_id: Optional[int] = None
    message: str
    errors: Optional[List[str]] = None
    options: Optional[List[dict]] = None   


class ProductUpdateRequest(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None  # used if id not provided

    # fields to update (all optional)
    new_name: Optional[str] = None
    list_price: Optional[float] = None
    standard_price: Optional[float] = None
    type: Optional[str] = None
    categ_name: Optional[str] = None
    barcode: Optional[str] = None
    description: Optional[str] = None
    uom_name: Optional[str] = None
    taxes_names: Optional[List[str]] = None    

class ProductDeleteRequest(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None    

# ============ Helper Functions ============

def get_default_values() -> dict:
    """Get default values from Odoo using product.template"""
    try:
        defaults = call_odoo("product.template", "default_get", [[]])
        if defaults:
            return defaults
    except:
        pass
    
    try:
        defaults = call_odoo("product.product", "default_get", [[]])
        if defaults:
            return defaults
    except:
        pass
    
    return {
        "type": "consu",
        "sale_ok": True,
        "purchase_ok": True
    }

def find_or_create_category(categ_name: str) -> tuple[int, Optional[str]]:
    """Find existing category or create new one. Returns (id, error)"""
    try:
        categories = call_odoo("product.category", "search_read", [
            [[["name", "=", categ_name]]],
            ["id", "name"]
        ])
        
        if categories:
            return categories[0]["id"], None
        
        new_id = call_odoo("product.category", "create", [[{"name": categ_name}]])
        return new_id, None
        
    except Exception as e:
        return None, str(e)

def find_uom(uom_name: str) -> tuple[int, Optional[str]]:
    """Find UoM by name. Returns (id, error)"""
    try:
        uoms = call_odoo("uom.uom", "search_read", [
            [[["name", "=", uom_name]]],
            ["id", "name"]
        ])
        
        if uoms:
            return uoms[0]["id"], None
        
        return None, f"UoM '{uom_name}' not found. Available: Unit, Kg, Hour, etc."
        
    except Exception as e:
        return None, str(e)

def find_taxes(taxes_names: List[str]) -> tuple[list, List[str]]:
    """Find taxes by names. Returns (tax_ids, errors)"""
    tax_ids = []
    errors = []
    
    for tax_name in taxes_names:
        try:
            taxes = call_odoo("account.tax", "search_read", [
                [[["name", "=", tax_name]]],
                ["id", "name"]
            ])
            
            if taxes:
                tax_ids.append(taxes[0]["id"])
            else:
                errors.append(f"Tax '{tax_name}' not found")
                
        except Exception as e:
            errors.append(f"Tax error for '{tax_name}': {str(e)}")
    
    return tax_ids, errors

def find_product_id(product_id: Optional[int], name: Optional[str]):
    try:
        if product_id:
            return product_id, None, None

        if name:
            # 1. exact match first
            products = call_odoo("product.product", "search_read", [
                [["name", "=", name]],
                ["id", "name"],
                0,
                10
            ])

            # 2. fallback ilike if nothing found
            if not products:
                products = call_odoo("product.product", "search_read", [
                    [["name", "ilike", name]],
                    ["id", "name"],
                    0,
                    10
                ])

            if not products:
                return None, f"Product '{name}' not found", None

            # 3. if multiple matches → return options
            if len(products) > 1:
                return None, "Multiple products found", [
                    {"id": p["id"], "name": p["name"]} for p in products
                ]

            return products[0]["id"], None, None

        return None, "Provide id or name", None

    except Exception as e:
        return None, str(e), None

# ============ Main Endpoints ============

@app.post("/product/create", response_model=ProductResponse)
async def create_product(request: ProductCreateRequest):
    """Create a product in Odoo"""
    errors = []
    
    try:
        defaults = get_default_values()
        values = dict(defaults)
        
        values["name"] = request.name
        
        if request.type is not None:
            values["type"] = request.type
        
        if request.list_price is not None:
            values["list_price"] = request.list_price
        
        if request.standard_price is not None:
            values["standard_price"] = request.standard_price
        
        if request.barcode:
            values["barcode"] = request.barcode
        
        if request.description:
            values["description_html"] = request.description
        
        if request.categ_name:
            categ_id, error = find_or_create_category(request.categ_name)
            if categ_id:
                values["categ_id"] = categ_id
            elif error:
                errors.append(f"Category issue: {error}")
        
        if request.uom_name:
            uom_id, error = find_uom(request.uom_name)
            if uom_id:
                values["uom_id"] = uom_id
                values["uom_po_id"] = uom_id
            elif error:
                errors.append(error)
        
        if request.taxes_names:
            tax_ids, tax_errors = find_taxes(request.taxes_names)
            errors.extend(tax_errors)
            if tax_ids:
                values["taxes_id"] = [[6, 0, tax_ids]]
        
        product_id = call_odoo("product.product", "create", [values])
        
        product_info = call_odoo("product.product", "read", [
            [product_id],
            ["name", "list_price", "type", "categ_id"]
        ])
        
        product_name = product_info[0]["name"]
        message = f"Product '{product_name}' created successfully (ID: {product_id})"
        
        if errors:
            message += f" | Warnings: {'; '.join(errors)}"
        
        return ProductResponse(
            success=True,
            product_id=product_id,
            message=message,
            errors=errors if errors else None
        )
        
    except Exception as e:
        return ProductResponse(
            success=False,
            message=f"Failed to create product: {str(e)}",
            errors=errors if errors else None
        )

@app.post("/product/list")
async def get_products(filters: ProductFilterRequest):
    """Fetch products from Odoo with optional filtering"""
    domain = []
    
    # Build Odoo Domain for filtering
    if filters.name:
        domain.append(["name", "ilike", filters.name])
    if filters.categ_id:
        domain.append(["categ_id", "=", filters.categ_id])

    try:
        products = call_odoo("product.product", "search_read", [
            domain,             # Filter criteria
            filters.fields,     # Fields to return
            filters.offset,     # Pagination offset
            filters.limit       # Record limit
        ])
        
        return {
            "success": True,
            "count": len(products),
            "data": products
        }
        
    except Exception as e:
        return {
            "success": False, 
            "message": f"Error fetching products: {str(e)}"
        }

# ============ Utility Endpoints ============

@app.get("/product/fields")
async def get_product_fields():
    """Get all available fields for product (for AI discovery)"""
    try:
        fields = call_odoo("product.product", "fields_get", [[]])
        
        relevant = {}
        skip_fields = ["id", "create_date", "write_date", "create_uid", "write_uid", "message_ids"]
        
        for field_name, field_info in fields.items():
            if field_name in skip_fields:
                continue
                
            if field_info.get("type") in ["char", "float", "integer", "many2one", "selection", "text", "boolean"]:
                relevant[field_name] = {
                    "string": field_info.get("string"),
                    "type": field_info.get("type"),
                    "required": field_info.get("required", False),
                    "help": field_info.get("help", "")[:200] if field_info.get("help") else None
                }
        
        defaults = get_default_values()
        
        return {
            "success": True,
            "fields": relevant,
            "defaults": defaults
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/health")
async def health_check():
    """Check if Odoo is reachable"""
    try:
        call_odoo("res.partner", "search", [[["id", "=", 1]]])
        return {
            "status": "ok",
            "odoo": "connected",
            "url": ODOO_URL,
            "database": ODOO_DB
        }
    except Exception as e:
        return {
            "status": "error",
            "odoo": f"disconnected: {str(e)}",
            "url": ODOO_URL,
            "database": ODOO_DB
        }
    
@app.post("/product/update", response_model=ProductResponse)
async def update_product(request: ProductUpdateRequest):
    """Smart update: works with id OR name and only updates provided fields"""
    errors = []

    try:
        # 1. Find product
        product_id, error, options = find_product_id(request.id, request.name)
        if error and options:
            return ProductResponse(success=False, message=error, options=options)

        values = {}

        # 2. Update only provided fields
        if request.new_name is not None:
            values["name"] = request.new_name

        if request.list_price is not None:
            values["list_price"] = request.list_price

        if request.standard_price is not None:
            values["standard_price"] = request.standard_price

        if request.type is not None:
            values["type"] = request.type

        if request.barcode is not None:
            values["barcode"] = request.barcode

        if request.description is not None:
            values["description_html"] = request.description

        # Category
        if request.categ_name:
            categ_id, error = find_or_create_category(request.categ_name)
            if categ_id:
                values["categ_id"] = categ_id
            elif error:
                errors.append(f"Category issue: {error}")

        # UOM
        if request.uom_name:
            uom_id, error = find_uom(request.uom_name)
            if uom_id:
                values["uom_id"] = uom_id
                values["uom_po_id"] = uom_id
            elif error:
                errors.append(error)

        # Taxes
        if request.taxes_names:
            tax_ids, tax_errors = find_taxes(request.taxes_names)
            errors.extend(tax_errors)
            if tax_ids:
                values["taxes_id"] = [[6, 0, tax_ids]]

        # 3. Nothing to update check
        if not values:
            return ProductResponse(
                success=False,
                message="No fields provided to update"
            )

        # 4. Update in Odoo
        call_odoo("product.product", "write", [[product_id], values])

        return ProductResponse(
            success=True,
            product_id=product_id,
            message=f"Product {product_id} updated successfully",
            errors=errors if errors else None
        )

    except Exception as e:
        return ProductResponse(
            success=False,
            message=f"Update failed: {str(e)}",
            errors=errors if errors else None
        )    
@app.post("/product/delete", response_model=ProductResponse)
async def delete_product(request: ProductDeleteRequest):
    """Smart delete: works with id OR name + handles duplicates"""

    try:
        product_id, error, options = find_product_id(request.id, request.name)

        # CASE: multiple products found
        if error and options:
            return ProductResponse(
                success=False,
                message=error,
                options=options
            )

        # CASE: not found
        if error:
            return ProductResponse(
                success=False,
                message=error
            )

        # DELETE in Odoo
        call_odoo("product.product", "unlink", [[product_id]])

        return ProductResponse(
            success=True,
            product_id=product_id,
            message=f"Product {product_id} deleted successfully"
        )

    except Exception as e:
        return ProductResponse(
            success=False,
            message=f"Delete failed: {str(e)}"
        )    

if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("Odoo Product Service Started")
    print(f"Odoo URL: {ODOO_URL}")
    print(f"Database: {ODOO_DB}")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)