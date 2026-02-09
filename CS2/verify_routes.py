from main import app
routes = [route.path for route in app.routes]
print(f"Routes: {routes}")

if "/ask" in routes and "/status" in routes:
    print("✅ Routes /ask and /status are correctly registered.")
else:
    print("❌ Routes missing.")
