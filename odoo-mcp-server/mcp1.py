from datetime import date
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
import xmlrpc.client
import json

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all for testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# Odoo config
# ---------------------------
URL = "http://host.docker.internal:8069"
DB = "school_odoo"
USERNAME = "admin"
PASSWORD = "odoo"

common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common")
UID = common.authenticate(DB, USERNAME, PASSWORD, {})
models = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object")

# ---------------------------
# Employee Model
# ---------------------------
class Employee(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    job_title: str | None = None
    department_id: int | None = None
    parent_id: int | None = None
    job_id: int | None = None

# ---------------------------
# CREATE EMPLOYEE TOOL
# ---------------------------
@app.post("/create_employee")
def create_employee(emp: Employee):
    try:
        data = {}
        if emp.name: data["name"] = emp.name
        if emp.email: data["work_email"] = emp.email
        if emp.phone: data["mobile_phone"] = emp.phone
        if emp.job_title: data["job_title"] = emp.job_title
        if emp.department_id: data["department_id"] = emp.department_id
        if emp.parent_id: data["parent_id"] = emp.parent_id
        if emp.job_id: data["job_id"] = emp.job_id

        employee_id = models.execute_kw(DB, UID, PASSWORD, "hr.employee", "create", [data])
        return {"status": "success", "employee_id": employee_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ---------------------------
# EDIT EMPLOYEE TOOL
# ---------------------------
@app.put("/edit_employee")
def edit_employee(employee_id: int = Query(...), emp: Employee = None):
    try:
        data = {}
        if emp.name: data["name"] = emp.name
        if emp.email: data["work_email"] = emp.email
        if emp.phone: data["mobile_phone"] = emp.phone
        if emp.job_title: data["job_title"] = emp.job_title
        if emp.department_id: data["department_id"] = emp.department_id
        if emp.parent_id: data["parent_id"] = emp.parent_id
        if emp.job_id: data["job_id"] = emp.job_id

        success = models.execute_kw(DB, UID, PASSWORD, "hr.employee", "write", [[employee_id], data])
        if success:
            return {"status": "success", "employee_id": employee_id}
        else:
            raise HTTPException(status_code=400, detail="Update failed")
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ---------------------------
# DELETE EMPLOYEE TOOL
# ---------------------------
@app.delete("/delete_employee")
def delete_employee(employee_id: int = Query(...)):
    try:
        success = models.execute_kw(DB, UID, PASSWORD, "hr.employee", "unlink", [[employee_id]])
        if success:
            return {"status": "success", "employee_id": employee_id}
        else:
            raise HTTPException(status_code=400, detail="Delete failed")
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ---------------------------
# GET EMPLOYEES TOOL
# ---------------------------
@app.get("/employees")
def get_employees(limit: int = 0):
    return models.execute_kw(
        DB, UID, PASSWORD,
        "hr.employee", "search_read",
        [[]],
        {"fields": ["id","name","work_email","mobile_phone","job_title","department_id","parent_id","job_id"], "limit": limit}
    )

# ---------------------------
# GET DEPARTMENTS TOOL
# ---------------------------
@app.get("/departments")
def get_departments():
    return models.execute_kw(DB, UID, PASSWORD, "hr.department", "search_read", [[]], {"fields": ["id","name"]})

# ---------------------------
# GET JOB POSITIONS TOOL
# ---------------------------
@app.get("/job_positions")
def get_job_positions():
    return models.execute_kw(DB, UID, PASSWORD, "hr.job", "search_read", [[]], {"fields": ["id","name"]})

# ---------------------------
# Archive Employee
# ---------------------------
class ArchiveEmployeeBody(BaseModel):
    departure_reason_id: int
    departure_date: str  # YYYY-MM-DD

@app.put("/archive_employee")
def archive_employee(employee_id: int = Query(...), body: ArchiveEmployeeBody = None):
    try:
        if body is None:
            raise HTTPException(status_code=400, detail="Request body required")
        try:
            date.fromisoformat(body.departure_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="departure_date must be YYYY-MM-DD")

        wizard_id = models.execute_kw(DB, UID, PASSWORD, "hr.departure.wizard", "create", [{
            "employee_ids": [(6, 0, [employee_id])],
            "departure_reason_id": body.departure_reason_id,
            "departure_date": body.departure_date,
            "set_date_end": True
        }])
        models.execute_kw(DB, UID, PASSWORD, "hr.departure.wizard", "action_confirm", [[wizard_id]])
        return {"status": "success", "employee_id": employee_id, "archived": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/departure_reasons")
def get_departure_reasons(name: str = None):
    domain = [["name", "ilike", name]] if name else []
    return models.execute_kw(DB, UID, PASSWORD, "hr.departure.reason", "search_read", [domain], {"fields": ["id","name"]})

# ---------------------------
# MCP Discovery Endpoints
# ---------------------------

@app.post("/mcp")
async def mcp_post(request: Request):
    manifest = {
        "type": "manifest",   # <-- required
        "name": "Odoo Employee MCP Server",
        "version": "1.0",
        "protocol": "mcp/1.0",  # <-- declare protocol version
        "tools_endpoint": "/tools",
        "description": "MCP-compatible server exposing Odoo HR tools"
    }

    async def event_generator():
        # Yield newline-delimited JSON message
        yield json.dumps(manifest) + "\n"

    return StreamingResponse(event_generator(), media_type="application/json")


@app.get("/mcp")
def get_mcp_info():
    return {
        "name": "Odoo Employee MCP Server",
        "version": "1.0",
        "tools_endpoint": "/tools",
        "description": "MCP-compatible server exposing Odoo HR tools"
    }


@app.get("/tools")
def get_tools():
    return [
        {
            "name": "create_employee",
            "description": "Create a new employee in Odoo",
            "method": "POST",
            "endpoint": "/create_employee",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "email": {"type": "string"},
                    "phone": {"type": "string"},
                    "job_title": {"type": "string"},
                    "department_id": {"type": "integer"},
                    "parent_id": {"type": "integer"},
                    "job_id": {"type": "integer"}
                },
                "required": ["name", "email"]
            },
            "output_schema": {"type": "object"}
        },
        {
            "name": "edit_employee",
            "description": "Edit an existing employee in Odoo",
            "method": "PUT",
            "endpoint": "/edit_employee",
            "input_schema": {
                "type": "object",
                "properties": {
                    "employee_id": {"type": "integer"},
                    "name": {"type": "string"},
                    "email": {"type": "string"},
                    "phone": {"type": "string"},
                    "job_title": {"type": "string"},
                    "department_id": {"type": "integer"},
                    "parent_id": {"type": "integer"},
                    "job_id": {"type": "integer"}
                }
            },
            "output_schema": {"type": "object"}
        },
        {
            "name": "delete_employee",
            "description": "Delete an existing employee in Odoo",
            "method": "DELETE",
            "endpoint": "/delete_employee",
            "input_schema": {
                "type": "object",
                "properties": {"employee_id": {"type": "integer"}},
                "required": ["employee_id"]
            },
            "output_schema": {"type": "object"}
        },
        {
            "name": "archive_employee",
            "description": "Archive (deactivate) an existing employee in Odoo",
            "method": "PUT",
            "endpoint": "/archive_employee",
            "input_schema": {
                "type": "object",
                "properties": {
                    "employee_id": {"type": "integer"},
                    "departure_reason_id": {"type": "integer"},
                    "departure_date": {"type": "string"}
                },
                "required": ["employee_id", "departure_reason_id", "departure_date"]
            },
            "output_schema": {"type": "object"}
        },
        {
            "name": "get_employees",
            "description": "Get list of employees",
            "method": "GET",
            "endpoint": "/employees",
            "input_schema": {
                "type": "object",
                "properties": {"limit": {"type": "integer"}}
            },
            "output_schema": {"type": "array"}
        },
        {
            "name": "get_departments",
            "description": "Get a list of all departments",
            "method": "GET",
            "endpoint": "/departments",
            "input_schema": {"type": "object"},
            "output_schema": {"type": "array"}
        },
        {
            "name": "get_job_positions",
            "description": "Get a list of all job positions",
            "method": "GET",
            "endpoint": "/job_positions",
            "input_schema": {"type": "object"},
            "output_schema": {"type": "array"}
        },
        {
            "name": "get_departure_reasons",
            "description": "Get a list of departure reasons",
            "method": "GET",
            "endpoint": "/departure_reasons",
            "input_schema": {
                "type": "object",
                "properties": {"name": {"type": "string"}}
            },
            "output_schema": {"type": "array"}
        }
    ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
