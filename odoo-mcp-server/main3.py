import os
import logging
import xmlrpc.client
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr

# ---------------------------
# Logging setup
# ---------------------------
logging.basicConfig(level=logging.INFO)

app = FastAPI()

# ---------------------------
# Odoo config (from env vars)
# ---------------------------
URL = os.getenv("ODOO_URL", "http://localhost:8069")
DB = os.getenv("ODOO_DB", "school_odoo")
USERNAME = os.getenv("ODOO_USER", "admin")
PASSWORD = os.getenv("ODOO_PASS", "odoo")

common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common")
UID = common.authenticate(DB, USERNAME, PASSWORD, {})
models = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object")

# ---------------------------
# Department Model
# ---------------------------
class Department(BaseModel):
    id: int | None = None
    name: str | None = None

# ---------------------------
# Employee Model
# ---------------------------
class Employee(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    job_title: str | None = None
    department: 1

# ---------------------------
# Helper: resolve department
# ---------------------------
def resolve_department(department: Department) -> int | None:
    if department.id:
        return department.id
    elif department.name:
        dept = models.execute_kw(
            DB, UID, PASSWORD,
            "hr.department", "search_read",
            [[["name", "ilike", department.name]]],
            {"fields": ["id", "name"]}
        )
        if not dept:
            raise HTTPException(status_code=404, detail=f"Department '{department.name}' not found")
        if len(dept) > 1:
            raise HTTPException(status_code=400, detail=f"Multiple departments match '{department.name}'")
        return dept[0]["id"]
    return None

# ---------------------------
# CREATE EMPLOYEE TOOL
# ---------------------------
@app.post("/create_employee")
def create_employee(emp: Employee):
    try:
        data = {
            "name": emp.name,
            "work_email": emp.email,
        }

        if emp.phone:
            data["mobile_phone"] = emp.phone
        if emp.job_title:
            data["job_title"] = emp.job_title
        if emp.department:
            data["department_id"] = resolve_department(emp.department)

        employee_id = models.execute_kw(
            DB, UID, PASSWORD,
            "hr.employee", "create",
            [data]
        )
        logging.info(f"Employee created: {emp.name} (ID {employee_id})")
        return {"status": "success", "employee_id": employee_id}

    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error("Error creating employee", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------------
# GET EMPLOYEES TOOL
# ---------------------------
@app.get("/employees")
def get_employees(limit: int = 10):
    return models.execute_kw(
        DB, UID, PASSWORD,
        "hr.employee", "search_read",
        [[]],
        {"fields": ["id", "name", "work_email", "department_id"], "limit": limit}
    )

# ---------------------------
# GET DEPARTMENTS TOOL
# ---------------------------
@app.get("/departments")
def get_departments():
    return models.execute_kw(
        DB, UID, PASSWORD,
        "hr.department", "search_read",
        [[]],
        {"fields": ["id", "name"]}
    )

# ---------------------------
# MCP-LIKE TOOL DISCOVERY
# ---------------------------
@app.get("/tools")
def get_tools():
    return [
        {
            "name": "create_employee",
            "description": "Create a new employee in Odoo",
            "method": "POST",
            "endpoint": "/create_employee",
            "parameters": {
                "name": "string (required)",
                "email": "string (required)",
                "phone": "string (optional)",
                "job_title": "string (optional)",
                "department": {
                    "id": "integer (optional)",
                    "name": "string (optional)"
                }
            }
        },
        {
            "name": "get_employees",
            "description": "Get list of employees for validation or reference",
            "method": "GET",
            "endpoint": "/employees",
            "parameters": {"limit": "integer (optional, default=10)"}
        },
        {
            "name": "get_departments",
            "description": "Get a list of all departments with their IDs",
            "method": "GET",
            "endpoint": "/departments",
            "parameters": {}
        }
    ]
