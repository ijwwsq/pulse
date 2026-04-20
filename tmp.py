import math


def mod_pow(base, exp, mod):
    result = 1
    base %= mod
    while exp > 0:
        if exp % 2 == 1:
            result = result * base % mod
        exp //= 2
        base = base * base % mod
    return result


def extended_gcd(a, b):
    if b == 0:
        return a, 1, 0
    g, x, y = extended_gcd(b, a % b)
    return g, y, x - (a // b) * y


def mod_inverse(a, m):
    g, x, _ = extended_gcd(a % m, m)
    if g != 1:
        raise ValueError("Обратного элемента не существует")
    return x % m


p = 17
q = 19
n = p * q
phi = (p - 1) * (q - 1)
e = 79

assert math.gcd(e, phi) == 1, "e и phi(n) должны быть взаимно простыми"

d = mod_inverse(e, phi)

assert (e * d) % phi == 1

print("=== Ключи RSA ===")
print(f"p={p}, q={q}, n={n}, phi(n)={phi}")
print(f"Открытый ключ: (e={e}, n={n})")
print(f"Закрытый ключ: (d={d}, n={n})")

m = 19
s = mod_pow(m, d, n)

print("\n=== Формирование ЭЦП ===")
print(f"Хэш-образ: m = {m}")
print(f"ЭЦП: s = {m}^{d} mod {n} = {s}")
print(f"Отправляем пару <M, s> = <сообщение, {s}>")


def verify_signature(m_hash, signature, e, n):
    m_restored = mod_pow(signature, e, n)
    return m_restored == m_hash, m_restored


messages = [
    (312, 122),
    (142, 29),
    (229, 134),
]

print("\n=== Проверка подлинности подписей ===")
print(f"{'m':>6} {'s':>6} {'s^e mod n':>10} {'Результат'}")
print("-" * 40)
for m_val, sig in messages:
    valid, restored = verify_signature(m_val, sig, e, n)
    status = "ПОДПИСЬ ВЕРНА" if valid else "ПОДПИСЬ НЕВЕРНА"
    print(f"{m_val:>6} {sig:>6} {restored:>10}   {status}")
