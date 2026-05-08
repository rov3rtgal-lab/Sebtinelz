import modal

app = modal.App("sentinel-cloud")

image = (
    modal.Image.debian_slim()
    .pip_install(
        "fastapi[standard]",
        "flask",
        "requests",
        "flask_sqlalchemy",
        "numpy",
        "pandas",
        "scikit-learn",
        "reportlab"
    )
    .add_local_dir(
        r"C:\Users\09-cf-rpolvorosa\OneDrive\Desktop\DPP\Project_Sentinel",
        remote_path="/root/project"
    )
)

@app.function(image=image)
@modal.fastapi_endpoint(method="GET")
def sentinel_api():
    return {
        "status": "Sentinel is live",
        "message": "Public API working 🚀"
    }