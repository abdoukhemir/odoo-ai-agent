from datetime import date

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, EmailStr
import xmlrpc.client

app = FastAPI()

# ---------------------------
# Odoo config
# ---------------------------
URL = "http://localhost:8069"
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
    parent_id: int | None = None   # <-- manager field
    job_id: int | None = None      # <-- job position field

# ---------------------------
# CREATE EMPLOYEE TOOL
# ---------------------------
@app.post("/create_employee")
def create_employee(emp: Employee):
    try:
        data = {}
        if emp.name:
            data["name"] = emp.name
        if emp.email:
            data["work_email"] = emp.email
        if emp.phone:
            data["mobile_phone"] = emp.phone
        if emp.job_title:
            data["job_title"] = emp.job_title
        if emp.department_id:
            data["department_id"] = emp.department_id
        if emp.parent_id:
            data["parent_id"] = emp.parent_id
        if emp.job_id:
            data["job_id"] = emp.job_id

        employee_id = models.execute_kw(
            DB, UID, PASSWORD,
            "hr.employee",
            "create",
            [data]
        )

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
        if emp.name:
            data["name"] = emp.name
        if emp.email:
            data["work_email"] = emp.email
        if emp.phone:
            data["mobile_phone"] = emp.phone
        if emp.job_title:
            data["job_title"] = emp.job_title
        if emp.department_id:
            data["department_id"] = emp.department_id
        if emp.parent_id:
            data["parent_id"] = emp.parent_id
        if emp.job_id:
            data["job_id"] = emp.job_id

        success = models.execute_kw(
            DB, UID, PASSWORD,
            "hr.employee",
            "write",
            [[employee_id], data]
        )

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
        success = models.execute_kw(
            DB, UID, PASSWORD,
            "hr.employee",
            "unlink",
            [[employee_id]]
        )

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
        "hr.employee",
        "search_read",
        [[]],
        {
            "fields": [
                "id",
                "name",
                "work_email",
                "mobile_phone",
                "job_title",
                "department_id",
                "parent_id",
                "job_id"
            ],
            "limit": limit
        }
    )

# ---------------------------
# GET DEPARTMENTS TOOL
# ---------------------------
@app.get("/departments")
def get_departments():
    return models.execute_kw(
        DB, UID, PASSWORD,
        "hr.department",
        "search_read",
        [[]],
        {"fields": ["id", "name"]}
    )

# ---------------------------
# GET JOB POSITIONS TOOL
# ---------------------------
@app.get("/job_positions")
def get_job_positions():
    return models.execute_kw(
        DB, UID, PASSWORD,
        "hr.job",
        "search_read",
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
                "department_id": "integer (optional)",
                "parent_id": "integer (optional, manager employee ID)",
                "job_id": "integer (optional, job position ID)"
            }
        },
        {
            "name": "edit_employee",
            "description": "Edit an existing employee in Odoo",
            "method": "PUT",
            "endpoint": "/edit_employee",
            "parameters": {
                "queryParameters": {
                    "employee_id": "integer (required, employee ID to edit, passed as query param)"
                },
                "body": {
                    "name": "string (optional)",
                    "email": "string (optional)",
                    "phone": "string (optional)",
                    "job_title": "string (optional)",
                    "department_id": "integer (optional)",
                    "parent_id": "integer (optional, manager employee ID)",
                    "job_id": "integer (optional, job position ID)"
                }
            }
        },
        {
            "name": "delete_employee",
            "description": "Delete an existing employee in Odoo",
            "method": "DELETE",
            "endpoint": "/delete_employee",
            "parameters": {
                "queryParameters": {
                    "employee_id": "integer (required, employee ID to delete, passed as query param)"
                }
            }
        },
        {
            "name": "get_employees",
            "description": "Get list of employees with all fields used in create_employee",
            "method": "GET",
            "endpoint": "/employees",
            "parameters": {"limit": "integer (optional, default=0)"}
        },
        {
            "name": "get_departments",
            "description": "Get a list of all departments with their IDs",
            "method": "GET",
            "endpoint": "/departments",
            "parameters": {}
        },
        {
            "name": "get_job_positions",
            "description": "Get a list of all job positions with their IDs",
            "method": "GET",
            "endpoint": "/job_positions",
            "parameters": {}
        }
    ]
# Add this at the very end of your file
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)