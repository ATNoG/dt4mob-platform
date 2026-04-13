from fastapi.staticfiles import StaticFiles
from fastapi.responses import ORJSONResponse, HTMLResponse
from fastapi import FastAPI
from .routers import events


root_path = "/historic"

app = FastAPI(root_path=root_path, docs_url=None, redoc_url=None,default_response_class=ORJSONResponse,title="Ditto Events API", description="API to manage historical events from Eclipse Ditto")

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(router=events.router)

@app.get("/", include_in_schema=False)
def custom_swagger_ui_html():
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <link type="text/css" rel="stylesheet" href="{root_path}/static/swagger-ui.css">
    <title>{app.title} - Swagger UI</title>
    </head>
    <body>
    <div id="swagger-ui"></div>
    <script src="{root_path}/static/swagger-ui-bundle.js"></script>
    <script src="{root_path}/static/swagger-ui-standalone-preset.js"></script>
    <script src="{root_path}/static/swagger-initializer.js"></script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)