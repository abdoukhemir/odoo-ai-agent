from datetime import date
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from fastapi.responses import JSONResponse, StreamingResponse
import xmlrpc.client
import json
import asyncio


app = FastAPI()


# ---------------------------
# Enable CORS (for dev only)
# ---------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
# Data models
# ---------------------------

class Employee(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    job_title: str | None = None
    department_id: int | None = None
    parent_id: int | None = None
    job_id: int | None = None


class ArchiveEmployeeBody(BaseModel):
    departure_reason_id: int
    departure_date: str  # YYYY-MM-DD


# ---------------------------
# JSON‑RPC helpers
# ---------------------------

def make_jsonrpc_response(id: int | None, result: dict | None = None, error: dict | None = None):
    base = {"jsonrpc": "2.0", "id": id}
    if error:
        base["error"] = error
    elif result is not None:
        base["result"] = result
    return base



def make_jsonrpc_error(id: int | None, code: int, message: str) -> dict:
    return make_jsonrpc_response(id, error={"code": code, "message": message})


# ---------------------------
# MCP tools spec (n8n will read this)
# ---------------------------

def get_mcp_tools():
    return [
        {
            "name": "create_employee",
            "description": "Create a new employee in Odoo",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "email": {"type": "string", "format": "email"},
                    "phone": {"type": "string"},
                    "job_title": {"type": "string"},
                    "department_id": {"type": "integer"},
                    "parent_id": {"type": "integer"},
                    "job_id": {"type": "integer"}
                },
                "required": ["name", "email"]
            },
            "outputSchema": {"type": "object"}
        },
        {
            "name": "edit_employee",
            "description": "Edit an existing employee in Odoo",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "employee_id": {"type": "integer"},
                    "name": {"type": "string"},
                    "email": {"type": "string", "format": "email"},
                    "phone": {"type": "string"},
                    "job_title": {"type": "string"},
                    "department_id": {"type": "integer"},
                    "parent_id": {"type": "integer"},
                    "job_id": {"type": "integer"}
                }
            },
            "outputSchema": {"type": "object"}
        },
        {
            "name": "delete_employee",
            "description": "Delete an existing employee in Odoo",
            "inputSchema": {
                "type": "object",
                "properties": {"employee_id": {"type": "integer"}},
                "required": ["employee_id"]
            },
            "outputSchema": {"type": "object"}
        },
        {
            "name": "archive_employee",
            "description": "Archive (deactivate) an existing employee in Odoo with a departure reason and date",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "employee_id": {"type": "integer"},
                    "departure_reason_id": {"type": "integer"},
                    "departure_date": {"type": "string", "format": "date"}
                },
                "required": ["employee_id", "departure_reason_id", "departure_date"]
            },
            "outputSchema": {"type": "object"}
        },
        {
            "name": "get_employees",
            "description": "Get list of employees",
            "inputSchema": {
                "type": "object",
                "properties": {"limit": {"type": "integer"}}
            },
            "outputSchema": {"type": "array"}
        },
        {
            "name": "get_departments",
            "description": "Get a list of all departments",
            "inputSchema": {"type": "object"},
            "outputSchema": {"type": "array"}
        },
        {
            "name": "get_job_positions",
            "description": "Get a list of all job positions",
            "inputSchema": {"type": "object"},
            "outputSchema": {"type": "array"}
        },
        {
            "name": "get_departure_reasons",
            "description": "Get a list of departure reasons",
            "inputSchema": {
                "type": "object",
                "properties": {"name": {"type": "string"}}
            },
            "outputSchema": {"type": "array"}
        }
    ]


# ---------------------------
# Odoo tool endpoints (keep these)
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


@app.put("/edit_employee")
def edit_employee(employee_id: int = Query(...), emp: Employee = None):
    try:
        data = {}
        if emp and emp.name: data["name"] = emp.name
        if emp and emp.email: data["work_email"] = emp.email
        if emp and emp.phone: data["mobile_phone"] = emp.phone
        if emp and emp.job_title: data["job_title"] = emp.job_title
        if emp and emp.department_id: data["department_id"] = emp.department_id
        if emp and emp.parent_id: data["parent_id"] = emp.parent_id
        if emp and emp.job_id: data["job_id"] = emp.job_id

        success = models.execute_kw(DB, UID, PASSWORD, "hr.employee", "write", [[employee_id], data])
        if success:
            return {"status": "success", "employee_id": employee_id}
        else:
            raise HTTPException(status_code=400, detail="Update failed")
    except Exception as e:
        return {"status": "error", "message": str(e)}


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


@app.get("/employees")
def get_employees(limit: int | None = None):
    lim = limit if limit is not None and limit > 0 else 0
    return models.execute_kw(
        DB, UID, PASSWORD,
        "hr.employee", "search_read",
        [[]],
        {"fields": ["id","name","work_email","mobile_phone","job_title","department_id","parent_id","job_id"], "limit": lim}
    )


@app.get("/departments")
def get_departments():
    return models.execute_kw(DB, UID, PASSWORD, "hr.department", "search_read", [[]], {"fields": ["id","name"]})


@app.get("/job_positions")
def get_job_positions():
    return models.execute_kw(DB, UID, PASSWORD, "hr.job", "search_read", [[]], {"fields": ["id","name"]})


@app.put("/archive_employee")
def archive_employee(employee_id: int = Query(...), body: ArchiveEmployeeBody = None):
    if body is None:
        raise HTTPException(status_code=400, detail="Request body required")

    try:
        date.fromisoformat(body.departure_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="departure_date must be YYYY-MM-DD")

    try:
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
def get_departure_reasons(name: str | None = None):
    if name:
        domain = [["name", "ilike", name]]
    else:
        domain = []
    return models.execute_kw(DB, UID, PASSWORD, "hr.departure.reason", "search_read", [domain], {"fields": ["id","name"]})


# ---------------------------
# MCP / Odoo tool router (mapping tool → your functions)
# ---------------------------

ODOO_TOOL_ROUTER = {
    "create_employee": {
        "method": "POST",
        "url": "/create_employee",
        "runner": lambda data: create_employee(Employee(**data))
    },
    "edit_employee": {
        "method": "PUT",
        "url": "/edit_employee",
        "runner": lambda data: edit_employee(
            employee_id=data["employee_id"],
            emp=Employee(**{k: v for k, v in data.items() if k != "employee_id"})
        )
    },
    "delete_employee": {
        "method": "DELETE",
        "url": "/delete_employee",
        "runner": lambda data: delete_employee(employee_id=data["employee_id"])
    },
    "archive_employee": {
        "method": "PUT",
        "url": "/archive_employee",
        "runner": lambda data: archive_employee(
            employee_id=data["employee_id"],
            body=ArchiveEmployeeBody(
                departure_reason_id=data["departure_reason_id"],
                departure_date=data["departure_date"]
            )
        )
    },
    "get_employees": {
        "method": "GET",
        "url": "/employees",
        "runner": lambda data: get_employees(limit=data.get("limit"))
    },
    "get_departments": {
        "method": "GET",
        "url": "/departments",
        "runner": lambda data: get_departments()
    },
    "get_job_positions": {
        "method": "GET",
        "url": "/job_positions",
        "runner": lambda data: get_job_positions()
    },
    "get_departure_reasons": {
        "method": "GET",
        "url": "/departure_reasons",
        "runner": lambda data: get_departure_reasons(name=data.get("name"))
    }
}


def sync_run_tool(tool_name: str, tool_input: dict | None) -> dict:
    spec = ODOO_TOOL_ROUTER.get(tool_name)
    if not spec:
        raise ValueError(f"unknown tool '{tool_name}'")

    if tool_input is None:
        tool_input = {}

    try:
        result = spec["runner"](tool_input)
        if isinstance(result, dict):
            return result
        else:
            # wrap list/other types into data
            return {"data": result}
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------
# MCP HTTP‑Streamable endpoint (for n8n)
# ---------------------------

@app.post("/mcp")
async def mcp_post(request: Request):
    body_raw = await request.body()
    body_text = body_raw.decode("utf‑8").strip()

    async def mcp_stream():
        request_id = 1

        # Step 1: initialize
        if "initialize" in body_text:
            yield json.dumps(
                make_jsonrpc_response(
                    id=request_id,
                    result={
                        "capabilities": {
                            "tools": {"toolMetadata": True},
                            "resources": {"resourceMetadata": False},
                            "prompts": {"promptMetadata": False}
                        },
                        "serverInfo": {
                            "name": "Odoo Employee MCP Server",
                            "version": "1.0",
                            "protocolVersion": "1.0"
                        }
                    }
                )
            ) + "\n"
            await asyncio.sleep(0.01)

        # Step 2: listTools
        if "listTools" in body_text:
            yield json.dumps(
                make_jsonrpc_response(
                    id=request_id + 1,
                    result={"tools": get_mcp_tools()}
                )
            ) + "\n"
            await asyncio.sleep(0.01)

        # Step 3: callTool
        if "callTool" in body_text:
            try:
                rpc = json.loads(body_text)
                if rpc.get("method") == "callTool":
                    params = rpc.get("params", {})
                    tool_name = params.get("name")
                    tool_input = params.get("input", None)

                    if not tool_name:
                        yield json.dumps(
                            make_jsonrpc_error(
                                id=rpc.get("id"),
                                code=400,
                                message="missing 'name' in callTool params"
                            )
                        ) + "\n"
                        return

                    result = sync_run_tool(tool_name, tool_input)
                    yield json.dumps(
                        make_jsonrpc_response(
                            id=rpc.get("id"),
                            result={"output": result}
                        )
                    ) + "\n"
            except Exception as e:
                yield json.dumps(
                    make_jsonrpc_error(
                        id=rpc.get("id") if "rpc" in globals() or "rpc" in dir() else None,
                        code=500,
                        message=str(e)
                    )
                ) + "\n"

    return StreamingResponse(mcp_stream(), media_type="application/x-ndjson")



# Optional: simple GET /mcp for sanity checks
@app.get("/mcp")
def get_mcp_info():
    return {
        "name": "Odoo Employee MCP Server",
        "version": "1.0",
        "tools_endpoint": "/mcp",
        "description": "MCP‑compatible HTTP‑Streamable server for Odoo HR tools"
    }


# ---------------------------
# Run the app
# ---------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
