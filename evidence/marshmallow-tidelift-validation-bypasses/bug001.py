from marshmallow import Schema, fields, validates, ValidationError
class S(Schema):
    name = fields.Str(attribute='a.b')
    @validates('name')
    def check(self, value, **kw):
        raise ValidationError('rejected')
for many, data in ((False, {'name': 'x'}), (True, [{'name': 'x'}])):
    try:
        print("many=%s result=%r" % (many, S(many=many).load(data)))
    except ValidationError as e:
        print("many=%s ValidationError %r" % (many, e.messages))
