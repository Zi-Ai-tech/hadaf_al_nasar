"""Route blueprints for the application."""

__all__ = ['register_all_blueprints']


def register_all_blueprints(app):
    """Register every required application blueprint.

    Required blueprint imports deliberately fail fast so an incomplete
    application cannot start successfully.
    """
    from app.routes.auth import auth_bp
    from app.routes.customers import customers_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.employee import employee_bp
    from app.routes.expense import expense_bp
    from app.routes.financial_report import financial_report_bp
    from app.routes.income import income_bp
    from app.routes.invoices import invoices_bp
    from app.routes.salary import salary_bp
    from app.routes.security import security_bp
    from app.routes.transport import transport_bp

    blueprints = (
        (auth_bp, None),
        (dashboard_bp, None),
        (customers_bp, '/accounts'),
        (invoices_bp, None),
        (employee_bp, None),
        (salary_bp, None),
        (expense_bp, None),
        (income_bp, None),
        (financial_report_bp, None),
        (transport_bp, None),
        (security_bp, None),
    )
    for blueprint, url_prefix in blueprints:
        app.register_blueprint(blueprint, url_prefix=url_prefix)
