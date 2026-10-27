from ml import predict_material

mat = predict_material("CFRP")
print("CFRP:", mat)

mat2 = predict_material("carbon fiber")   # thử cách gọi tên khác
print("So khop alias?", mat == mat2)

try:
    predict_material("titanium")
except ValueError as e:
    print("Loi ro rang khi vat lieu khong co:", e)