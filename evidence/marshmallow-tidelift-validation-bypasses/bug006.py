from marshmallow import Schema, fields, INCLUDE
class S(Schema):
    class Meta:
        unknown = INCLUDE
    first_name = fields.Int(data_key='firstName')
print("data_key collision:", S().load({'firstName': '5', 'first_name': 'evil'}))
class T(Schema):
    class Meta:
        unknown = INCLUDE
    x = fields.Int(attribute='y')
print("attribute collision:", T().load({'x': '1', 'y': 'evil'}))
