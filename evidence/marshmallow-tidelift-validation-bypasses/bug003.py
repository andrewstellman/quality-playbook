from marshmallow import Schema, fields, ValidationError
class Inner(Schema):
    a = fields.Int()
    b = fields.Int()
class Outer(Schema):
    by_class = fields.Nested(Inner)
    by_instance = fields.Nested(Inner())
payload = {"by_class": {"a": 1, "b": 2}, "by_instance": {"a": 1, "b": 2}}
print("dump with load_only:", Outer(load_only=('by_class.b', 'by_instance.b')).dump(payload))
try:
    print("load with dump_only:", Outer(dump_only=('by_class.b', 'by_instance.b')).load(payload))
except ValidationError as e:
    print("load with dump_only: ValidationError", e.messages)
