from backend.main import create_app

app = create_app()
print('Registered routes:')
for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
    methods = ','.join(sorted(rule.methods))
    print(f'{rule.rule:40} -> {rule.endpoint:30} [{methods}]')
