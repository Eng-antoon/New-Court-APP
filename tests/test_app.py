import pytest

def test_routes_registered(app):
    """Check that all routes are properly registered"""
    
    # Get all registered routes
    rules = list(app.url_map.iter_rules())
    route_endpoints = [rule.endpoint for rule in rules]
    
    # Print all registered routes for debugging
    print("\n\n==== REGISTERED ROUTES ====")
    for rule in rules:
        print(f"Route: {rule.rule}, Endpoint: {rule.endpoint}, Methods: {rule.methods}")
    print("==========================\n\n")
    
    # Check for key routes
    assert 'reservations.get_reservations' in route_endpoints
    assert 'reservations.create_reservation' in route_endpoints
    assert 'courts.get_courts' in route_endpoints
    assert 'auth.login' in route_endpoints 