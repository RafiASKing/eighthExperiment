import bcrypt
password = b"passwordnya" # Ganti password rahasia kamu
hashed = bcrypt.hashpw(password, bcrypt.gensalt())
print(hashed)