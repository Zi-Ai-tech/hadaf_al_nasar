# test_actual_structure.py
from app import create_app

app = create_app()

with app.app_context():
    print("=== Testing Actual Model Structure ===\n")
    
    # Import from the correct locations
    from app.models.core.user import User
    from app.models.core.customer import Customer
    from app.models.wps.employee import Employee
    from app.models.wps.expense import Expense
    from app.models.wps.income import Income
    from app.models.logistics.vehicle import Vehicle
    from app.models.logistics.driver import Driver
    
    print("✅ Successfully imported models from correct locations")
    
    # Check the models
    models_to_check = [
        ('User', User, 'app.models.core.user'),
        ('Customer', Customer, 'app.models.core.customer'),
        ('Employee', Employee, 'app.models.wps.employee'),
        ('Vehicle', Vehicle, 'app.models.logistics.vehicle'),
        ('Driver', Driver, 'app.models.logistics.driver'),
        ('Expense', Expense, 'app.models.wps.expense'),
        ('Income', Income, 'app.models.wps.income'),
    ]
    
    for name, model, expected_path in models_to_check:
        actual_module = model.__module__
        if expected_path in actual_module:
            print(f"✅ {name} imported from correct location: {actual_module}")
        else:
            print(f"⚠️  {name} imported from unexpected location: {actual_module}")
    
    print("\n=== Testing Database Tables ===")
    
    from app import db
    from sqlalchemy import text
    
    session = db.session
    
    # Check if tables exist
    tables_to_check = [
        ('user', User),
        ('customer', Customer),
        ('employee', Employee),
        ('vehicle', Vehicle),
        ('driver', Driver),
        ('expense', Expense),
        ('income', Income),
    ]
    
    for table_name, model in tables_to_check:
        try:
            result = session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            count = result.scalar()
            print(f"✅ {table_name}: {count} records")
        except Exception as e:
            print(f"⚠️  {table_name} query failed: {e}")
    
    print("\n=== Testing Relationships ===")
    
    # Test if relationships are set up correctly
    try:
        # Check Vehicle relationships
        if hasattr(Vehicle, 'current_driver'):
            print("✅ Vehicle has current_driver relationship")
        if hasattr(Vehicle, 'maintenance_records'):
            print("✅ Vehicle has maintenance_records relationship")
        
        # Check Driver relationships
        if hasattr(Driver, 'current_vehicle'):
            print("✅ Driver has current_vehicle relationship")
        
        # Check Expense relationships
        if hasattr(Expense, 'vehicle'):
            print("✅ Expense has vehicle relationship")
        if hasattr(Expense, 'employee'):
            print("✅ Expense has employee relationship")
        
        # Check Income relationships
        if hasattr(Income, 'vehicle'):
            print("✅ Income has vehicle relationship")
        if hasattr(Income, 'customer'):
            print("✅ Income has customer relationship")
            
    except Exception as e:
        print(f"⚠️  Relationship check failed: {e}")
    
    print("\n=== All tests completed ===")
