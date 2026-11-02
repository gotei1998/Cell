import json
import math
import re

import sympy as sp
from sympy.integrals.manualintegrate import integral_steps
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)
FUNCS = "asin|acos|atan|acot|sinh|cosh|tanh|coth|sin|cos|tan|cot|log|exp|sqrt"
WORDS = [
    ("arcsin", "asin"), ("arccos", "acos"), ("arctg", "atan"), ("arctan", "atan"),
    ("arcctg", "acot"), ("arccot", "acot"), ("ctg", "cot"), ("cotg", "cot"), ("tg", "tan"),
    ("cth", "coth"), ("sh", "sinh"), ("ch", "cosh"), ("th", "tanh"), ("ln", "log"),
    ("inf", "oo"), ("infinity", "oo"), ("бесконечность", "oo"),
]


class UserError(Exception):
    pass


class Unsolved(Exception):
    pass


def normalize(s):
    s = s.strip()
    for a, b in [("х", "x"), ("Х", "x"), ("у", "y"), ("е", "e"), ("а", "a"), ("с", "c"),
                 ("π", "pi"), ("∞", "oo"), ("−", "-"), ("–", "-"), ("·", "*"), ("×", "*"),
                 ("÷", "/"), ("√", "sqrt"), ("²", "^2"), ("³", "^3"), ("’", "'")]:
        s = s.replace(a, b)
    s = re.sub(r"(\d),(\d)", r"\1.\2", s)
    s = re.sub(r"\b(lg|ln|log)\^(\d+)\s*\(([^()]*)\)", r"(\1(\3))^\2", s)
    s = re.sub(r"log_?\{([^{}]+)\}\s*\(", r"LOGBASE((\1),", s)
    s = re.sub(r"log_\(([^()]+)\)\s*\(", r"LOGBASE((\1),", s)
    s = re.sub(r"log_?(\d+(?:\.\d+)?|[a-z])\s*\(", r"LOGBASE(\1,", s)
    s = re.sub(r"log_?(\d+(?:\.\d+)?|[a-z])\s+([a-z0-9.]+)", r"LOGBASE(\1,\2)", s)
    for a, b in WORDS:
        s = re.sub(rf"(?<![A-Za-z_]){a}(?![A-Za-z_])", b, s)
        s = re.sub(rf"(?<![A-Za-z_]){a}(?=[xyztnk\d])", b + " ", s)
    return re.sub(rf"(?<![A-Za-z_])({FUNCS})(?=[a-z0-9])(?!h)", r"\1 ", s)


def parse(s, extra=None, what="выражение"):
    if not s or not s.strip():
        raise UserError(f"Заполните поле: {what}.")
    local = {"e": sp.E, "pi": sp.pi, "E": sp.E, "oo": sp.oo,
             "lg": lambda v: sp.log(v, 10), "I": sp.I, "LOGBASE": lambda a, v: sp.log(v, a)}
    local.update(extra or {})
    try:
        expr = parse_expr(normalize(s), local_dict=local, transformations=TRANSFORMS)
    except Exception:
        raise UserError(f"Не удалось разобрать запись «{s.strip()}». Проверьте скобки и знаки "
                        "умножения, например: x^2*sin(x).")
    if isinstance(expr, sp.Expr):
        return sp.nsimplify(expr, rational=True) if expr.has(sp.Float) else expr
    raise UserError(f"В записи «{s.strip()}» нет математического выражения.")


def symbol(s, default="x"):
    s = normalize(s or default)
    if not re.fullmatch(r"[A-Za-z]", s):
        raise UserError("Переменная должна быть одной латинской буквой, например x.")
    return sp.Symbol(s)


def L(e):
    t = sp.latex(e, ln_notation=True, inv_trig_style="full")
    for a, b in [(r"\tan", r"\operatorname{tg}"), (r"\cot", r"\operatorname{ctg}"),
                 (r"\arctan", r"\operatorname{arctg}"), (r"\operatorname{acot}", r"\operatorname{arcctg}"),
                 (r"\operatorname{arccot}", r"\operatorname{arcctg}"),
                 (r"\sinh", r"\operatorname{sh}"), (r"\cosh", r"\operatorname{ch}"),
                 (r"\tanh", r"\operatorname{th}"), (r"\coth", r"\operatorname{cth}")]:
        t = re.sub(re.escape(a) + r"(?![a-zA-Z])", lambda _: b, t)
    return t


def M(e):
    return r"\(" + (e if isinstance(e, str) else L(e)) + r"\)"


class Work:
    def __init__(self):
        self.steps = []
        self.tags = []

    def add(self, text, math=None, depth=0):
        self.steps.append({"text": text, "math": math, "depth": depth})

    def tag(self, t):
        if t not in self.tags:
            self.tags.append(t)


def is_true(e):
    try:
        return sp.simplify(e) == 0
    except Exception:
        return False


def sample(f, x):
    fn = sp.lambdify(x, f, modules="math")
    pts = []
    for i in range(241):
        v = -6 + i * 0.05
        try:
            y = fn(v)
            y = float(y) if not isinstance(y, complex) and math.isfinite(y) else None
        except Exception:
            y = None
        pts.append([round(v, 3), y])
    return pts if sum(1 for p in pts if p[1] is not None) > 10 else None


def plot(x, *series):
    out = []
    for name, f in series:
        if isinstance(f, sp.Expr) and f.free_symbols <= {x}:
            try:
                pts = sample(f, x)
            except Exception:
                pts = None
            if pts:
                out.append({"name": name, "latex": L(f), "points": pts})
    return out


# ---------- Производные ----------

TABLE = {
    sp.sin: r"(\sin u)' = \cos u", sp.cos: r"(\cos u)' = -\sin u",
    sp.tan: r"(\operatorname{tg} u)' = \frac{1}{\cos^2 u}",
    sp.cot: r"(\operatorname{ctg} u)' = -\frac{1}{\sin^2 u}",
    sp.exp: r"(e^u)' = e^u", sp.log: r"(\ln u)' = \frac{1}{u}",
    sp.asin: r"(\arcsin u)' = \frac{1}{\sqrt{1-u^2}}",
    sp.acos: r"(\arccos u)' = -\frac{1}{\sqrt{1-u^2}}",
    sp.atan: r"(\operatorname{arctg} u)' = \frac{1}{1+u^2}",
    sp.sinh: r"(\operatorname{sh} u)' = \operatorname{ch} u",
    sp.cosh: r"(\operatorname{ch} u)' = \operatorname{sh} u",
}


def d_eq(f, x):
    return rf"\left({L(f)}\right)'_{{{L(x)}}} = {L(sp.diff(f, x))}"


def chain_note(w, u, x, d):
    if u != x:
        w.tag("chain")
        w.add(f"Функция сложная: внутренняя функция {M(rf'u = {L(u)}')}, её производная "
              f"{M(rf'u^\prime = {L(sp.diff(u, x))}')}.", None, d)


def diff_walk(w, f, x, d=0):
    if d > 4:
        return w.add("Дальше по тем же правилам.", d_eq(f, x), d)
    if not f.has(x):
        return w.add("Производная константы равна нулю.", d_eq(f, x), d)
    if f == x:
        return w.add("Производная самой переменной равна 1.", d_eq(f, x), d)
    if f.is_Add:
        w.tag("diff_rules")
        w.add("Производная суммы равна сумме производных.", d_eq(f, x), d)
        for t in f.args:
            diff_walk(w, t, x, d + 1)
        return
    if f.is_Mul:
        c, rest = f.as_independent(x)
        if c != 1:
            w.add(f"Выносим постоянный множитель {M(c)}.", d_eq(f, x), d)
            return diff_walk(w, rest, x, d + 1)
        n, m = f.as_numer_denom()
        if m.has(x) and m != 1 and not (f.args and all(a.is_Pow and a.exp.is_negative for a in f.args)):
            w.tag("diff_rules")
            w.add(f"Производная частного: {M(r'(u/v)^\prime = (u^\prime v - u v^\prime)/v^2')}, "
                  f"где {M(rf'u = {L(n)}')}, {M(rf'v = {L(m)}')}.", d_eq(f, x), d)
            diff_walk(w, n, x, d + 1)
            return diff_walk(w, m, x, d + 1)
        u, v = f.args[0], sp.Mul(*f.args[1:])
        w.tag("diff_rules")
        w.add(f"Производная произведения: {M(r'(uv)^\prime = u^\prime v + u v^\prime')}, "
              f"где {M(rf'u = {L(u)}')}, {M(rf'v = {L(v)}')}.", d_eq(f, x), d)
        diff_walk(w, u, x, d + 1)
        return diff_walk(w, v, x, d + 1)
    if f.is_Pow:
        b, e = f.as_base_exp()
        if not e.has(x):
            w.add(f"Степенная функция: {M(r'(u^n)^\prime = n u^{n-1} u^\prime')}.", d_eq(f, x), d)
            chain_note(w, b, x, d)
            if b != x:
                diff_walk(w, b, x, d + 1)
            return
        if not b.has(x):
            w.add(f"Показательная функция: {M(r'(a^u)^\prime = a^u \ln a \cdot u^\prime')}.", d_eq(f, x), d)
            chain_note(w, e, x, d)
            if e != x:
                diff_walk(w, e, x, d + 1)
            return
        w.tag("log_diff")
        return w.add("И основание, и показатель зависят от переменной. Применяем логарифмическое "
                     f"дифференцирование: {M(r'(\ln y)^\prime = y^\prime / y')}.", d_eq(f, x), d)
    if isinstance(f, sp.Function) and len(f.args) == 1:
        rule = TABLE.get(type(f))
        w.add("Табличная производная: " + M(rule) + "." if rule else "Табличная производная.", d_eq(f, x), d)
        u = f.args[0]
        chain_note(w, u, x, d)
        if u != x:
            diff_walk(w, u, x, d + 1)
        return
    w.add("Дифференцируем.", d_eq(f, x), d)


def solve_derivative(t):
    x = symbol(t.get("var"))
    f = parse(t.get("f"), what="функция")
    n = int(t.get("order") or 1)
    if not 1 <= n <= 10:
        raise UserError("Порядок производной должен быть от 1 до 10.")
    w = Work()
    w.tag("derivative")
    diff_walk(w, f, x)
    cur = sp.diff(f, x)
    for k in range(2, n + 1):
        nxt = sp.diff(cur, x)
        w.add(f"Дифференцируем ещё раз и получаем производную порядка {k}.",
              rf"y^{{({k})}} = {L(sp.simplify(nxt))}")
        cur = nxt
    ans = sp.simplify(cur)
    if len(str(ans)) > len(str(cur)):
        ans = cur
    prime = "'" * n if n < 4 else f"^{{({n})}}"
    head = rf"\left({L(f)}\right){prime}"
    return {
        "problem": head + " = \\;?", "answer": rf"{head} = {L(ans)}", "work": w,
        "check": check_numeric(sp.Derivative(f, (x, n)).doit() - ans, x,
                               "Ответ сверен с независимым вычислением в нескольких точках."),
        "plot": plot(x, ("f", f), ("производная", ans)),
    }


def check_numeric(diff, x, text):
    pts = [sp.Rational(7, 10), sp.Rational(13, 10), sp.Rational(23, 10)]
    try:
        vals = [abs(sp.N(diff.subs(x, p))) for p in pts]
        return {"ok": all(v < 1e-9 for v in vals if v.is_finite), "text": text}
    except Exception:
        return None


# ---------- Интегралы ----------

ATOMIC = {
    "ConstantRule": "Интеграл константы.",
    "PowerRule": r"Степенная функция: \(\int x^n\,dx = \frac{x^{n+1}}{n+1} + C\).",
    "ReciprocalRule": r"Табличный интеграл: \(\int \frac{dx}{x} = \ln|x| + C\).",
    "ExpRule": r"Показательная функция: \(\int a^x\,dx = \frac{a^x}{\ln a} + C\).",
    "SinRule": r"Табличный интеграл: \(\int \sin x\,dx = -\cos x + C\).",
    "CosRule": r"Табличный интеграл: \(\int \cos x\,dx = \sin x + C\).",
    "Sec2Rule": r"Табличный интеграл: \(\int \frac{dx}{\cos^2 x} = \operatorname{tg} x + C\).",
    "Csc2Rule": r"Табличный интеграл: \(\int \frac{dx}{\sin^2 x} = -\operatorname{ctg} x + C\).",
    "ArctanRule": r"Табличный интеграл: \(\int \frac{dx}{a^2+x^2} = \frac{1}{a}\operatorname{arctg}\frac{x}{a} + C\).",
    "ArcsinRule": r"Табличный интеграл: \(\int \frac{dx}{\sqrt{1-x^2}} = \arcsin x + C\).",
    "SinhRule": r"Табличный интеграл: \(\int \operatorname{sh} x\,dx = \operatorname{ch} x + C\).",
    "CoshRule": r"Табличный интеграл: \(\int \operatorname{ch} x\,dx = \operatorname{sh} x + C\).",
}


def int_eq(r):
    f, x = r.integrand, r.variable
    return rf"\int {L(f)}\,d{L(x)} = {L(r.eval())}"


def int_walk(w, r, d=0):
    name = type(r).__name__
    f, x = r.integrand, r.variable
    I = rf"\int {L(f)}\,d{L(x)}"
    if name == "AddRule":
        w.add("Интеграл суммы разбиваем на сумму интегралов.", I + " = " + " + ".join(
            rf"\int {L(s.integrand)}\,d{L(x)}" for s in r.substeps), d)
        for s in r.substeps:
            int_walk(w, s, d + 1)
    elif name == "ConstantTimesRule":
        w.add(f"Выносим постоянный множитель {M(r.constant)} за знак интеграла.",
              rf"{I} = {L(r.constant)} \int {L(r.other)}\,d{L(x)}", d)
        int_walk(w, r.substep, d + 1)
    elif name == "URule":
        w.tag("substitution")
        du = sp.diff(r.u_func, x)
        w.add(f"Делаем замену {M(rf'{L(r.u_var)} = {L(r.u_func)}')}, тогда "
              f"{M(rf'd{L(r.u_var)} = {L(du)}\,d{L(x)}')}.", None, d)
        int_walk(w, r.substep, d + 1)
        w.add("Возвращаемся к исходной переменной.", int_eq(r), d)
    elif name == "PartsRule":
        w.tag("parts")
        w.add(f"Интегрируем по частям: {M(r'\int u\,dv = uv - \int v\,du')}. Берём "
              f"{M(rf'u = {L(r.u)}')} и {M(rf'dv = {L(r.dv)}\,d{L(x)}')}.", None, d)
        v = r.v_step.eval()
        du = sp.diff(r.u, x)
        w.add(f"Тогда {M(rf'du = {L(du)}\,d{L(x)}')} и {M(rf'v = {L(v)}')}.", None, d)
        if r.second_step:
            w.add("Подставляем в формулу и получаем новый, более простой интеграл.",
                  rf"{I} = {L(r.u * v)} - \int {L(v * du)}\,d{L(x)}", d)
            int_walk(w, r.second_step, d + 1)
        w.add("Собираем результат.", int_eq(r), d)
    elif name == "CyclicPartsRule":
        w.tag("parts")
        w.add("Интегрируем по частям дважды. Исходный интеграл появляется снова, поэтому "
              "выражаем его из полученного уравнения.", int_eq(r), d)
    elif name in ("RewriteRule", "CompleteSquareRule"):
        w.add("Преобразуем подынтегральное выражение.", rf"{I} = \int {L(r.rewritten)}\,d{L(x)}", d)
        int_walk(w, r.substep, d + 1)
    elif name == "AlternativeRule":
        int_walk(w, r.alternatives[0], d)
    elif name == "RationalRule" or "Partial" in name:
        w.tag("partial_fractions")
        w.add("Раскладываем дробь на простейшие и интегрируем слагаемые.", int_eq(r), d)
    else:
        text = ATOMIC.get(name, "Берём интеграл.")
        w.add(text, int_eq(r), d)


def has_unknown(r):
    if type(r).__name__ == "DontKnowRule":
        return True
    for v in vars(r).values():
        for s in v if isinstance(v, (list, tuple)) else [v]:
            if type(s).__module__.endswith("manualintegrate") and has_unknown(s):
                return True
    return False


def solve_integral(t):
    x = symbol(t.get("var"))
    f = parse(t.get("f"), what="подынтегральная функция")
    a, b = (t.get("a") or "").strip(), (t.get("b") or "").strip()
    w = Work()
    w.tag("integral")
    F = None
    try:
        rule = integral_steps(f, x)
        if not has_unknown(rule):
            int_walk(w, rule)
            F = rule.eval()
    except Exception:
        w.steps.clear()
        F = None
    if F is None or not check_antiderivative(f, F, x):
        F = sp.integrate(f, x)
        w.steps.clear()
        w.add("Разобрать этот интеграл на простые шаги не получилось. Первообразная найдена "
              "алгоритмом символьного интегрирования (метод Риша и его расширения).")
    closed = not F.has(sp.Integral)
    if closed:
        G = sp.simplify(F)
        F = G if len(str(G)) <= len(str(F)) and (F.has(sp.pi) or not G.has(sp.pi)) else F
    if bool(a) != bool(b):
        raise UserError("Для определённого интеграла укажите оба предела или оставьте оба поля пустыми.")
    if a:
        lo, hi = parse(a, what="нижний предел"), parse(b, what="верхний предел")
        I = rf"\int_{{{L(lo)}}}^{{{L(hi)}}} {L(f)}\,d{L(x)}"
        val = sp.integrate(f, (x, lo, hi))
        w.tag("newton")
        if closed and lo.is_finite and hi.is_finite:
            w.add("Применяем формулу Ньютона — Лейбница.",
                  rf"\left.{L(F)}\right|_{{{L(lo)}}}^{{{L(hi)}}}", 0)
        if val.has(sp.Integral):
            num = sp.N(sp.Integral(f, (x, lo, hi)))
            return {"problem": I, "answer": rf"{I} \approx {L(num)}", "work": w, "check": None,
                    "plot": plot(x, ("f", f)), "note": "Точное значение не выражается через элементарные функции, показано приближённое."}
        approx = rf" \approx {sp.N(val, 8)}" if val.is_number and val.is_finite and not val.is_Rational else ""
        chk = None
        if val.is_number and val.is_finite and lo.is_finite and hi.is_finite:
            try:
                ok = abs(sp.N(sp.Integral(f, (x, lo, hi))) - sp.N(val)) < 1e-6
                chk = {"ok": bool(ok), "text": "Значение совпало с численным интегрированием."}
            except Exception:
                chk = None
        return {"problem": I, "answer": rf"{I} = {L(val)}{approx}", "work": w, "check": chk,
                "plot": plot(x, ("f", f))}
    I = rf"\int {L(f)}\,d{L(x)}"
    if not closed:
        return {"problem": I, "answer": I, "work": w, "check": None, "plot": plot(x, ("f", f)),
                "note": "Эта первообразная не выражается через элементарные функции."}
    res = {"problem": I, "answer": rf"{I} = {L(with_abs(F, f, x))} + C", "work": w,
           "check": {"ok": check_antiderivative(f, F, x),
                     "text": "Производная ответа равна подынтегральной функции."},
           "plot": plot(x, ("f", f), ("первообразная", F))}
    if F.has(sp.Si, sp.Ci, sp.Ei, sp.li, sp.erf, sp.erfi, sp.fresnels, sp.fresnelc):
        res["note"] = "Первообразная не элементарна, поэтому ответ записан через специальную функцию."
    return res


def with_abs(F, f, x):
    if f.has(sp.log):
        return F
    r = sp.Symbol(x.name, real=True)
    return F.replace(lambda e: isinstance(e, sp.log) and not e.args[0].subs(x, r).is_positive,
                     lambda e: sp.log(sp.Abs(e.args[0])))


def check_antiderivative(f, F, x):
    d = sp.diff(F, x) - f
    if is_true(d):
        return True
    return bool(check_numeric(d, x, "") and check_numeric(d, x, "")["ok"])


# ---------- Пределы ----------

def solve_limit(t):
    x = symbol(t.get("var"))
    f = parse(t.get("f"), what="функция")
    a = parse(t.get("point"), what="точка")
    side = t.get("side") or "+-"
    if side not in ("+", "-", "+-"):
        side = "+-"
    if a in (sp.oo, -sp.oo):
        side = "-" if a == sp.oo else "+"
    mark = {"+": "+0", "-": "-0"}.get(side, "") if a.is_finite else ""
    head = rf"\lim_{{{L(x)} \to {L(a)}{mark}}}"
    p = rf"{head} {L(f)}"
    val = sp.limit(f, x, a, side) if a.is_finite else sp.limit(f, x, a)
    w = Work()
    w.tag("limit")
    cur = f
    n, m = cur.as_numer_denom()
    def lim(e):
        return sp.limit(e, x, a, "+" if side == "+-" else side)
    if m.has(x):
        for _ in range(3):
            ln, lm = lim(n), lim(m)
            kind = None
            if ln == 0 and lm == 0:
                kind = r"\frac{0}{0}"
            elif abs(ln) == sp.oo and abs(lm) == sp.oo:
                kind = r"\frac{\infty}{\infty}"
            if not kind:
                w.add(f"Числитель стремится к {M(ln)}, знаменатель к {M(lm)}. Неопределённости нет, "
                      "поэтому предел находим подстановкой.")
                break
            w.tag("lhopital")
            w.add(f"Неопределённость {M(kind)}. Применяем правило Лопиталя: заменяем числитель и "
                  "знаменатель их производными.",
                  rf"{head} \frac{{{L(n)}}}{{{L(m)}}} = {head} \frac{{{L(sp.diff(n, x))}}}{{{L(sp.diff(m, x))}}}")
            n, m = sp.diff(n, x), sp.diff(m, x)
    else:
        w.add("Находим значение предела.", rf"{p} = {L(val)}")
    if side == "+-" and a.is_finite:
        l, r = sp.limit(f, x, a, "-"), sp.limit(f, x, a, "+")
        if l != r:
            w.add(f"Односторонние пределы различны: слева {M(l)}, справа {M(r)}.")
            return {"problem": p, "answer": rf"{p} \text{{ не существует}}", "work": w,
                    "check": {"ok": True, "text": "Сравнены пределы слева и справа."},
                    "plot": plot(x, ("f", f))}
    chk = None
    if a.is_finite and val.is_finite and val.is_number:
        eps = sp.Rational(1, 100000)
        s = 1 if side == "+-" or side == "+" else -1
        try:
            near = sp.N(f.subs(x, a + s * eps))
            chk = {"ok": bool(abs(near - sp.N(val)) < 1e-2),
                   "text": "Значение функции рядом с точкой совпало с пределом."}
        except Exception:
            chk = None
    return {"problem": p, "answer": rf"{p} = {L(val)}", "work": w, "check": chk, "plot": plot(x, ("f", f))}


# ---------- Ряды ----------

def solve_sum(t):
    n = symbol(t.get("var"), "n")
    a = parse(t.get("f"), what="общий член")
    lo = parse(t.get("a") or "1", what="начало")
    hi = parse(t.get("b") or "oo", what="конец")
    S = sp.Sum(a, (n, lo, hi))
    p = L(S)
    w = Work()
    w.tag("series")
    if hi == sp.oo:
        lim = sp.limit(a, n, sp.oo)
        if lim != 0:
            w.add(f"Необходимое условие сходимости не выполнено: {M(rf'\lim a_{{n}} = {L(lim)} \neq 0')}.")
            return {"problem": p, "answer": rf"{p} \text{{ расходится}}", "work": w,
                    "check": {"ok": True, "text": "Общий член не стремится к нулю."}, "plot": []}
        w.add(f"Необходимое условие выполнено: {M(r'\lim_{n \to \infty} a_n = 0')}.")
        ratio = None
        try:
            ratio = sp.limit(sp.simplify(sp.Abs(a.subs(n, n + 1) / a)), n, sp.oo)
        except Exception:
            pass
        if ratio is not None and ratio.is_number:
            w.tag("dalembert")
            verdict = "ряд сходится" if ratio < 1 else "ряд расходится" if ratio > 1 else "признак не даёт ответа"
            w.add(f"Признак Даламбера: {M(rf'q = \lim_{{n\to\infty}} |a_{{n+1}}/a_n| = {L(ratio)}')}, {verdict}.")
        conv = S.is_convergent()
        if not conv:
            return {"problem": p, "answer": rf"{p} \text{{ расходится}}", "work": w, "check": None, "plot": []}
    val = S.doit()
    if val.has(sp.Sum):
        num = sp.N(S)
        return {"problem": p, "answer": rf"{p} \approx {L(num)}", "work": w, "check": None, "plot": [],
                "note": "Ряд сходится, но точная сумма не нашлась, показано приближённое значение."}
    val = sp.simplify(val)
    w.add("Находим сумму в замкнутом виде.", rf"{p} = {L(val)}")
    chk = None
    if hi != sp.oo and hi.is_number and hi - lo < 200:
        chk = {"ok": is_true(sum(a.subs(n, k) for k in range(int(lo), int(hi) + 1)) - val),
               "text": "Совпало с прямым сложением всех членов."}
    elif hi == sp.oo and val.is_number:
        part = sp.N(sp.Sum(a, (n, lo, lo + 4000)))
        chk = {"ok": bool(abs(part - sp.N(val)) < 0.01), "text": "Частичная сумма из 4000 членов близка к ответу."}
    return {"problem": p, "answer": rf"{p} = {L(val)}", "work": w, "check": chk, "plot": []}


def solve_taylor(t):
    x = symbol(t.get("var"))
    f = parse(t.get("f"), what="функция")
    a = parse(t.get("point") or "0", what="точка")
    n = int(t.get("order") or 5)
    if not 1 <= n <= 20:
        raise UserError("Порядок разложения должен быть от 1 до 20.")
    w = Work()
    w.tag("taylor")
    w.add("Находим производные в точке разложения и подставляем их в формулу Тейлора.")
    poly, cur = sp.Integer(0), f
    for k in range(n + 1):
        v = cur.subs(x, a)
        if not v.is_finite:
            v = sp.limit(cur, x, a)
        if not v.is_finite:
            raise UserError("В этой точке функция не разлагается в ряд Тейлора: производная не определена.")
        w.add(f"Производная порядка {k}.", rf"f^{{({k})}}({L(a)}) = {L(v)}", 1)
        poly += v * (x - a) ** k / sp.factorial(k)
        cur = sp.diff(cur, x)
    p = rf"{L(f)}, \quad {L(x)} \to {L(a)}"
    return {"problem": p, "answer": rf"{L(f)} = {L(poly)} + o\left({L(x) if a == 0 else "(" + L(x - a) + ")"}^{{{n}}}\right)", "work": w,
            "check": {"ok": is_true(sp.diff(poly, x, n).subs(x, a) - sp.diff(f, x, n).subs(x, a)),
                      "text": "Старшая производная многочлена совпала с производной функции."},
            "plot": plot(x, ("f", f), ("многочлен Тейлора", poly))}


# ---------- Матрицы ----------

def parse_matrix(s):
    rows = [r for r in re.split(r"[\n;]+", s.strip()) if r.strip()]
    if not rows:
        raise UserError("Заполните матрицу: каждая строка с новой строки, числа через пробел.")
    data = [[parse(c, what="элемент матрицы") for c in re.split(r"[\s,]+", r.strip()) if c] for r in rows]
    if len({len(r) for r in data}) != 1:
        raise UserError("В строках матрицы разное число элементов.")
    return sp.Matrix(data)


def gauss(w, A, split=None, reduce=False):
    A = A.copy()
    rows, cols = A.shape
    limit = split or cols
    r, sign, pivots = 0, 1, []
    def show(M_):
        body = L(M_)
        if split:
            spec = "c" * split + "|" + "c" * (cols - split)
            body = body.replace(r"\begin{matrix}", r"\begin{array}{" + spec + "}").replace(r"\end{matrix}", r"\end{array}")
        return body
    for c in range(limit):
        piv = next((i for i in range(r, rows) if A[i, c] != 0), None)
        if piv is None:
            continue
        if piv != r:
            A.row_swap(piv, r)
            sign = -sign
            w.add(f"Меняем местами строки {r + 1} и {piv + 1}.", show(A), 1)
        ops = []
        for i in range(r + 1 if not reduce else 0, rows):
            if i != r and A[i, c] != 0:
                k = A[i, c] / A[r, c]
                A[i, :] = A[i, :] - k * A[r, :]
                ops.append(rf"R_{{{i + 1}}} \to R_{{{i + 1}}} - {sp.latex(k) if k.is_positive else '(' + sp.latex(k) + ')'}\,R_{{{r + 1}}}")
        if reduce and A[r, c] != 1:
            k = A[r, c]
            A[r, :] = A[r, :] / k
            ops.append(rf"R_{{{r + 1}}} \to R_{{{r + 1}}} / {'(' + sp.latex(k) + ')' if k < 0 else sp.latex(k)}")
        if ops:
            w.add("Операции: " + M(r",\quad ".join(ops)) + ".", show(A), 1)
        pivots.append(c)
        r += 1
        if r == rows:
            break
    return A, sign, pivots


def solve_matrix(t):
    A = parse_matrix(t.get("matrix") or "")
    op = t.get("op") or "det"
    numeric = all(e.is_number for e in A)
    w = Work()
    w.tag("matrix")
    a = L(A)
    square = A.rows == A.cols
    if op in ("det", "inv", "eigen") and not square:
        raise UserError("Для этой операции матрица должна быть квадратной.")
    if op == "det":
        d = A.det()
        if numeric:
            w.tag("gauss")
            w.add("Приводим матрицу к треугольному виду методом Гаусса. Прибавление строки не меняет "
                  "определитель, а перестановка строк меняет его знак.")
            U, sign, _ = gauss(w, A)
            diag = [U[i, i] for i in range(A.rows)]
            w.add("Определитель равен произведению чисел на диагонали"
                  + (" с учётом смены знака." if sign < 0 else "."),
                  rf"\det A = {'-' if sign < 0 else ''}" + r" \cdot ".join(f"({L(v)})" for v in diag) + f" = {L(d)}")
        return {"problem": rf"\det {a}", "answer": rf"\det A = {L(sp.simplify(d))}", "work": w,
                "check": {"ok": is_true(d - A.berkowitz_det()),
                          "text": "Совпало с вычислением другим алгоритмом."}, "plot": []}
    if op == "inv":
        d = A.det()
        if is_true(d):
            w.add(f"Определитель равен нулю: {M(r'\det A = 0')}. Обратной матрицы не существует.")
            return {"problem": rf"{a}^{{-1}}", "answer": r"\text{Обратной матрицы нет}", "work": w,
                    "check": None, "plot": []}
        inv = A.inv().applyfunc(sp.simplify)
        if numeric:
            w.tag("gauss")
            w.add("Приписываем справа единичную матрицу и приводим левую часть к единичной.")
            gauss(w, A.row_join(sp.eye(A.rows)), split=A.cols, reduce=True)
        return {"problem": rf"{a}^{{-1}}", "answer": rf"A^{{-1}} = {L(inv)}", "work": w,
                "check": {"ok": (A * inv).applyfunc(sp.simplify) == sp.eye(A.rows),
                          "text": "Произведение матрицы на ответ дало единичную матрицу."}, "plot": []}
    if op == "rank":
        rank = A.rank()
        if numeric:
            w.tag("gauss")
            w.add("Приводим матрицу к ступенчатому виду. Ранг равен числу ненулевых строк.")
            gauss(w, A)
        return {"problem": rf"\operatorname{{rank}} {a}", "answer": rf"\operatorname{{rank}} A = {rank}", "work": w,
                "check": {"ok": rank == A.T.rank(), "text": "Ранг транспонированной матрицы такой же."}, "plot": []}
    if op == "eigen":
        lam = sp.Symbol("lambda")
        cp = (A - lam * sp.eye(A.rows)).det().expand()
        w.tag("eigen")
        w.add("Составляем характеристическое уравнение.", rf"\det(A - \lambda E) = {L(sp.factor(cp))} = 0")
        ok, lines = True, []
        for val, mult, vecs in A.eigenvects():
            w.add(f"Для {M(rf'\lambda = {L(val)}')} (кратность {mult}) решаем "
                  f"{M(r'(A - \lambda E)v = 0')}.", ", ".join(L(v) for v in vecs), 1)
            lines.append(rf"\lambda = {L(val)}: \quad " + ", ".join(L(v) for v in vecs))
            ok = ok and all((A * v - val * v).applyfunc(sp.simplify).is_zero_matrix for v in vecs)
        return {"problem": rf"\text{{Собственные значения }} {a}", "answer": r" \\ ".join(lines), "work": w,
                "check": {"ok": ok, "text": "Для каждого вектора выполнено Av = λv."}, "plot": []}
    raise UserError("Неизвестная операция с матрицей.")


# ---------- Уравнения ----------

def to_eq(line):
    if line.count("=") > 1:
        raise UserError("В одной строке должен быть один знак равенства.")
    if "=" in line:
        l, r = line.split("=")
        return parse(l, what="левая часть"), parse(r, what="правая часть")
    return parse(line, what="уравнение"), sp.Integer(0)


def solve_equation(t):
    lines = [l for l in re.split(r"[\n;]+", t.get("f") or "") if l.strip()]
    if not lines:
        raise UserError("Введите уравнение, например: x^2 - 5x + 6 = 0.")
    pairs = [to_eq(l) for l in lines]
    exprs = [a - b for a, b in pairs]
    syms = sorted(set().union(*[e.free_symbols for e in exprs]), key=lambda s: s.name)
    if not syms:
        raise UserError("В уравнении нет неизвестных.")
    if len(exprs) > 1:
        return solve_system(pairs, exprs, syms)
    (l, r), e = pairs[0], exprs[0]
    x = syms[-1] if t.get("var") in (None, "") and len(syms) == 1 else symbol(t.get("var"))
    if x not in syms:
        x = syms[0]
    p = rf"{L(l)} = {L(r)}"
    w = Work()
    w.tag("equation")
    if r != 0:
        w.add("Переносим всё в левую часть.", rf"{L(sp.expand(e))} = 0")
    fac = sp.factor(e)
    if fac != sp.expand(e) and fac != e and fac.is_Mul:
        w.add("Раскладываем на множители. Произведение равно нулю, когда нулю равен хотя бы один множитель.",
              rf"{L(fac)} = 0")
    deg = sp.Poly(e, x).degree() if e.is_polynomial(x) else None
    if deg == 2:
        a, b, c = sp.Poly(e, x).all_coeffs()
        w.tag("quadratic")
        w.add("Квадратное уравнение: считаем дискриминант.",
              rf"D = b^2 - 4ac = {L(sp.expand(b**2 - 4 * a * c))}")
    sol = sp.solveset(e, x, sp.S.Reals)
    if isinstance(sol, sp.FiniteSet):
        roots = list(sol)
        ok = all(is_true(e.subs(x, v)) or abs(sp.N(e.subs(x, v))) < 1e-9 for v in roots)
        if roots:
            return {"problem": p, "answer": ", ".join(rf"{L(x)}_{{{i + 1}}} = {L(v)}" for i, v in enumerate(roots)) if len(roots) > 1 else rf"{L(x)} = {L(roots[0])}",
                    "work": w, "check": {"ok": ok, "text": "Подстановка корней обращает уравнение в верное равенство."},
                    "plot": plot(x, ("левая часть", e))}
    if sol is sp.S.EmptySet:
        comp = sp.solve(e, x)
        ans = r"\text{Действительных корней нет}"
        if comp:
            w.add("На действительной оси корней нет. Комплексные корни:",
                  ", ".join(L(v) for v in comp))
            ans += r"; \quad " + ", ".join(rf"{L(x)} = {L(v)}" for v in comp)
        return {"problem": p, "answer": ans, "work": w, "check": None, "plot": plot(x, ("левая часть", e))}
    if isinstance(sol, sp.ConditionSet):
        found = []
        for s in [-10, -3, -1, 0.5, 1, 3, 10]:
            try:
                v = sp.nsolve(e, x, s)
                if not any(abs(v - o) < 1e-8 for o in found) and sp.im(v) == 0:
                    found.append(v)
            except Exception:
                pass
        if not found:
            raise Unsolved()
        return {"problem": p, "answer": ", ".join(rf"{L(x)} \approx {sp.N(v, 8)}" for v in found), "work": w,
                "check": None, "plot": plot(x, ("левая часть", e)),
                "note": "Точную формулу найти не удалось, показаны приближённые корни. Могут быть и другие."}
    return {"problem": p, "answer": rf"{L(x)} \in {L(sol)}", "work": w,
            "check": None, "plot": plot(x, ("левая часть", e))}


def solve_system(pairs, exprs, syms):
    p = r"\begin{cases}" + r" \\ ".join(rf"{L(a)} = {L(b)}" for a, b in pairs) + r"\end{cases}"
    w = Work()
    w.tag("equation")
    linear = all(e.is_polynomial(*syms) and sp.Poly(e, *syms).total_degree() <= 1 for e in exprs)
    if linear:
        A, b = sp.linear_eq_to_matrix(exprs, syms)
        w.tag("gauss")
        w.add("Система линейная. Записываем расширенную матрицу и применяем метод Гаусса.")
        gauss(w, A.row_join(b), split=A.cols, reduce=True)
        sol = sp.linsolve((A, b), *syms)
        if sol is sp.S.EmptySet:
            w.add("Появилось противоречие вида 0 = c, где c ≠ 0.")
            return {"problem": p, "answer": r"\text{Решений нет}", "work": w,
                    "check": {"ok": True, "text": "Ранги основной и расширенной матриц различны."}, "plot": []}
        tup = list(sol)[0]
        ok = all(is_true(e.subs(dict(zip(syms, tup)))) for e in exprs)
        return {"problem": p, "answer": r",\quad ".join(rf"{L(s)} = {L(v)}" for s, v in zip(syms, tup)), "work": w,
                "check": {"ok": ok, "text": "Подстановка решения обращает все уравнения в верные равенства."}, "plot": []}
    sols = sp.solve(exprs, syms, dict=True)
    if not sols:
        raise Unsolved()
    w.add("Система нелинейная. Выражаем одну неизвестную через другую и подставляем.")
    ok = all(abs(sp.N(e.subs(s))) < 1e-9 for s in sols for e in exprs if not e.subs(s).free_symbols)
    return {"problem": p, "answer": r" \\ ".join(r",\quad ".join(rf"{L(k)} = {L(v)}" for k, v in s.items()) for s in sols),
            "work": w, "check": {"ok": ok, "text": "Подстановка каждого решения обращает все уравнения в верные равенства."}, "plot": []}


# ---------- Дифференциальные уравнения ----------

ODE_NAMES = {
    "separable": ("Уравнение с разделяющимися переменными.", "separable"),
    "1st_linear": ("Линейное уравнение первого порядка: ищем решение через интегрирующий множитель.", "first_linear"),
    "Bernoulli": ("Уравнение Бернулли: замена сводит его к линейному.", "first_linear"),
    "1st_exact": ("Уравнение в полных дифференциалах.", None),
    "1st_homogeneous_coeff_best": ("Однородное уравнение: делаем замену y = ux.", None),
    "1st_homogeneous_coeff_subs_dep_div_indep": ("Однородное уравнение: делаем замену y = ux.", None),
    "nth_linear_constant_coeff_homogeneous": ("Линейное однородное уравнение с постоянными коэффициентами.", "const_coeff"),
    "nth_linear_constant_coeff_undetermined_coefficients": ("Линейное неоднородное уравнение: общее решение равно сумме решения однородного и частного решения.", "const_coeff"),
    "nth_linear_constant_coeff_variation_of_parameters": ("Линейное неоднородное уравнение: частное решение ищем вариацией постоянных.", "const_coeff"),
}


def solve_ode(t):
    x = sp.Symbol("x")
    y = sp.Function("y")
    src = t.get("f") or ""

    def to_expr(s):
        s = normalize(s)
        s = re.sub(r"y('+)", lambda m: f"D{len(m.group(1))}_", s)
        s = re.sub(r"(?<![A-Za-z_])y(?![A-Za-z_(])", "D0_", s)
        return s

    local = {f"D{k}_": y(x).diff(x, k) if k else y(x) for k in range(0, 7)}
    local["y"] = y
    if not src.strip():
        raise UserError("Введите уравнение, например: y'' + y = sin(x).")
    parts = to_expr(src).split("=")
    if len(parts) > 2:
        raise UserError("В уравнении должен быть один знак равенства.")
    l = parse(parts[0], local, "левая часть")
    r = parse(parts[1], local, "правая часть") if len(parts) == 2 else sp.Integer(0)
    if not l.has(sp.Derivative) and not r.has(sp.Derivative):
        raise UserError("В уравнении нет производной. Записывайте её штрихом: y'.")
    eq = sp.Eq(l, r)
    ics = {}
    for part in re.split(r"[,;\n]+", t.get("ics") or ""):
        if not part.strip():
            continue
        m = re.fullmatch(r"\s*y('*)\(([^)]+)\)\s*=\s*(.+?)\s*", normalize(part))
        if not m:
            raise UserError("Начальные условия записывайте так: y(0)=1, y'(0)=0.")
        k, at, val = len(m.group(1)), parse(m.group(2)), parse(m.group(3))
        key = y(at) if k == 0 else y(x).diff(x, k).subs(x, at)
        ics[key] = val
    w = Work()
    w.tag("ode")
    hints = sp.classify_ode(eq, y(x))
    name = next((ODE_NAMES[h] for h in hints if h in ODE_NAMES), None)
    if name:
        w.add(name[0])
        if name[1]:
            w.tag(name[1])
    order = sp.ode_order(eq, y(x))
    if name and name[1] == "const_coeff":
        k_ = sp.Symbol("k")
        e = (eq.lhs - eq.rhs).expand()
        coeffs = {j: e.coeff(y(x).diff(x, j) if j else y(x)) for j in range(order + 1)}
        char = sum(c * k_ ** j for j, c in coeffs.items())
        w.add("Составляем характеристическое уравнение.", rf"{L(char)} = 0")
        rts = sp.roots(char, k_)
        if rts:
            w.add("Его корни:", ", ".join(rf"k = {L(v)}" + (rf"\ (\text{{кратность }} {m})" if m > 1 else "") for v, m in rts.items()))
    try:
        sol = sp.dsolve(eq, y(x), ics=ics or None)
    except Exception:
        raise Unsolved()
    sol0 = sol[0] if isinstance(sol, list) else sol
    all_sol = sol if isinstance(sol, list) else [sol]
    ok = all(sp.checkodesol(eq, s)[0] is True for s in all_sol)
    pl = plot(x, ("y", sol0.rhs)) if ics else []
    return {"problem": L(eq).replace(r"\frac{d}{d x} y{\left(x \right)}", "y'") + (r",\quad " + ", ".join(L(k) + " = " + L(v) for k, v in ics.items()) if ics else ""),
            "answer": r" \\ ".join(L(s) for s in all_sol), "work": w,
            "check": {"ok": ok, "text": "Подстановка решения обратно в уравнение дала тождество."}, "plot": pl}


# ---------- Логарифмы ----------

class Lg(sp.Function):
    """Логарифм, который не вычисляется сам, чтобы решение можно было показать по шагам."""
    nargs = 2

    def _latex(self, printer, exp=None):
        a, b = self.args
        name = r"\ln" if a == sp.E else r"\lg" if a == 10 else rf"\log_{{{printer._print(a)}}}"
        name += rf"^{{{printer._print(exp)}}}" if exp is not None else ""
        return rf"{name}\left({printer._print(b)}\right)"


LOG_LOCAL = {"LOGBASE": Lg, "log": lambda v: Lg(sp.E, v), "lg": lambda v: Lg(10, v)}


def plain(e):
    return e.replace(lambda a: isinstance(a, Lg), lambda a: sp.log(a.args[1], a.args[0]))


def combine(e):
    """Сводит логарифмы с одним основанием: log_a x + log_a y = log_a(xy)."""
    groups, rest = {}, []
    for term in sp.Add.make_args(e):
        c, part = term.as_coeff_Mul()
        if isinstance(part, Lg) and c.is_Rational:
            groups.setdefault(part.args[0], []).append((c, part.args[1]))
        else:
            rest.append(term)
    out = list(rest)
    for base, items in groups.items():
        arg = sp.Mul(*[v ** c for c, v in items]) if len(items) > 1 else None
        out.append(Lg(base, sp.simplify(arg)) if arg is not None else items[0][0] * Lg(base, items[0][1]))
    return sp.Add(*out)


def log_atoms(e, x=None):
    atoms = sorted(e.atoms(Lg), key=str)
    return [a for a in atoms if x is None or a.has(x)]


def in_domain(atoms, x, v):
    try:
        for a in atoms:
            arg, base = a.args[1].subs(x, v), a.args[0].subs(x, v)
            if not (sp.N(arg) > 0 and sp.N(base) > 0 and sp.simplify(base - 1) != 0):
                return False
        return True
    except TypeError:
        return False


def domain_step(w, atoms, x):
    conds = []
    for a in atoms:
        if a.args[1].has(x):
            conds.append(rf"{L(a.args[1])} > 0")
        if a.args[0].has(x):
            conds += [rf"{L(a.args[0])} > 0", rf"{L(a.args[0])} \neq 1"]
    w.tag("log_domain")
    w.add("Записываем область допустимых значений: под логарифмом стоит положительное число, "
          "основание положительно и не равно 1.", r",\quad ".join(dict.fromkeys(conds)))


def exact(v):
    n = sp.N(v, 30)
    if v.is_Rational or not n.is_number:
        return v
    guess = sp.nsimplify(n, rational=True, tolerance=1e-22)
    return guess if guess.is_Rational and guess.q < 1000 else v


def log_value(w, e):
    w.tag("log_def")
    for a in log_atoms(e):
        v = exact(plain(a))
        if v.is_Rational:
            w.add(f"По определению логарифма: {M(rf'{L(a.args[0])}^{{{L(v)}}} = {L(a.args[1])}')}.", rf"{L(a)} = {L(v)}")
    c = combine(e)
    if c != e:
        w.tag("log_props")
        w.add("Сумма логарифмов с одним основанием равна логарифму произведения, разность равна "
              "логарифму частного, а множитель переходит в показатель степени.", rf"{L(e)} = {L(c)}")
    val = exact(sp.simplify(plain(c)))
    ok = bool(abs(sp.N(plain(e) - val, 20)) < 1e-12)
    approx = rf" \approx {sp.N(val, 8)}" if val.is_number and not val.is_Rational else ""
    return {"problem": L(e), "answer": rf"{L(e)} = {L(val)}{approx}", "work": w,
            "check": {"ok": ok, "text": "Совпало с вычислением по исходному выражению с точностью 20 знаков."}, "plot": []}


def log_equation(w, l, r, x):
    e = l - r
    atoms = log_atoms(e, x)
    p = rf"{L(l)} = {L(r)}"
    domain_step(w, atoms, x)
    cand = None
    if len(atoms) == 1:
        t = sp.Symbol("t")
        q = sp.expand(e).subs(atoms[0], t)
        if not q.has(x) and q.is_polynomial(t) and sp.Poly(q, t).degree() >= 2:
            w.tag("log_sub")
            w.add(f"Делаем замену {M(rf't = {L(atoms[0])}')}.", rf"{L(q)} = 0")
            ts = sp.solve(q, t)
            w.add("Корни для новой переменной:", ", ".join(rf"t = {L(v)}" for v in ts))
            cand = []
            for v in ts:
                cand += sp.solve(plain(atoms[0]) - v, x)
    if cand is None:
        cl, cr = combine(l), combine(r)
        if (cl, cr) != (l, r):
            w.tag("log_props")
            w.add("Сводим логарифмы с одним основанием в один.", rf"{L(cl)} = {L(cr)}")
        if isinstance(cr, Lg) and not isinstance(cl, Lg):
            cl, cr = cr, cl
        if isinstance(cl, Lg) and isinstance(cr, Lg) and cl.args[0] == cr.args[0]:
            w.add("Основания равны, поэтому приравниваем выражения под логарифмами.", rf"{L(cl.args[1])} = {L(cr.args[1])}")
            cand = sp.solve(cl.args[1] - cr.args[1], x)
        elif isinstance(cl, Lg) and not cr.has(x):
            w.tag("log_def")
            pw = cl.args[0] ** cr
            w.add("По определению логарифма переходим к равенству без логарифма.", rf"{L(cl.args[1])} = {L(pw)}")
            cand = sp.solve(cl.args[1] - pw, x)
        else:
            cand = sp.solve(plain(e), x)
    roots, rejected = [], []
    for v in dict.fromkeys(cand):
        if v.is_real is not False and in_domain(atoms, x, v):
            roots.append(v)
        else:
            rejected.append(v)
    if rejected:
        w.add("Эти значения не входят в область допустимых значений и отбрасываются:",
              ", ".join(rf"{L(x)} = {L(v)}" for v in rejected))
    pl = plot(x, ("левая часть", plain(l)), ("правая часть", plain(r)))
    if not roots:
        return {"problem": p, "answer": r"\text{Решений нет}", "work": w, "check": None, "plot": pl}
    ok = all(abs(sp.N(plain(e).subs(x, v))) < 1e-9 for v in roots)
    return {"problem": p, "answer": ", ".join(rf"{L(x)} = {L(v)}" for v in roots), "work": w,
            "check": {"ok": ok, "text": "Подстановка корней в исходное уравнение дала верное равенство."}, "plot": pl}


def log_inequality(w, l, op, r, x):
    x_real = sp.Symbol(x.name, real=True)
    e = l - r
    atoms = log_atoms(e, x)
    tex = {"<": "<", ">": ">", "<=": r"\leq", ">=": r"\geq"}[op]
    p = rf"{L(l)} {tex} {L(r)}"
    domain_step(w, atoms, x)
    cl, cr = combine(l), combine(r)
    reduced = None
    if isinstance(cl, Lg) and not cr.has(x) and not cl.args[0].has(x):
        w.tag("log_ineq")
        rising = sp.N(cl.args[0]) > 1
        new = {"<": ">", ">": "<", "<=": r"\geq", ">=": r"\leq"}[op] if not rising else tex
        w.add("Основание больше 1, логарифм возрастает, поэтому знак неравенства сохраняется." if rising
              else "Основание меньше 1, логарифм убывает, поэтому знак неравенства меняется на противоположный.",
              rf"{L(cl.args[1])} {new} {L(cl.args[0] ** cr)}")
        back = {">": "<", "<": ">", ">=": "<=", "<=": ">="}
        reduced = (cl.args[1] - cl.args[0] ** cr, op if rising else back[op])
    dom = sp.S.Reals
    for a in atoms:
        dom &= sp.solve_univariate_inequality(a.args[1].subs(x, x_real) > 0, x_real, relational=False)
        if a.args[0].has(x):
            raise Unsolved()
    rels = {"<": sp.Lt, ">": sp.Gt, "<=": sp.Le, ">=": sp.Ge}
    if reduced:
        rel = rels[reduced[1]](reduced[0].subs(x, x_real), 0)
    else:
        rel = rels[op](plain(e).subs(x, x_real), 0)
    sol = sp.solve_univariate_inequality(rel, x_real, relational=False) & dom
    w.add("Объединяем результат с областью допустимых значений.", rf"{L(x)} \in {L(sol)}")
    fn = sp.lambdify(x_real, plain(e).subs(x, x_real), modules="math")
    cmp_ = {"<": lambda v: v < 0, ">": lambda v: v > 0, "<=": lambda v: v <= 0, ">=": lambda v: v >= 0}[op]
    ok = True
    for i in range(1, 400):
        v = sp.Rational(i, 8) - 25
        if dom.contains(v) == sp.true:
            ok = ok and bool(cmp_(fn(float(v)))) == (sol.contains(v) == sp.true)
    return {"problem": p, "answer": rf"{L(x)} \in {L(sol)}", "work": w,
            "check": {"ok": ok, "text": "Ответ сверен с неравенством в точках области определения."},
            "plot": plot(x, ("левая часть", plain(l)), ("правая часть", plain(r)))}


def solve_logs(t):
    s = (t.get("f") or "").replace("≤", "<=").replace("≥", ">=")
    if not s.strip():
        raise UserError("Введите выражение, например: log_2(8) + lg(100).")
    w = Work()
    w.tag("log_def")
    parts = re.split(r"(<=|>=|<|>)", s)
    if len(parts) == 3:
        l, r = parse(parts[0], LOG_LOCAL, "левая часть"), parse(parts[2], LOG_LOCAL, "правая часть")
        kind = parts[1]
    elif len(parts) == 1 and "=" in s:
        if s.count("=") > 1:
            raise UserError("В одной строке должен быть один знак равенства.")
        a, b = s.split("=")
        l, r, kind = parse(a, LOG_LOCAL, "левая часть"), parse(b, LOG_LOCAL, "правая часть"), "="
    elif len(parts) == 1:
        return log_value(w, parse(s, LOG_LOCAL))
    else:
        raise UserError("Запишите одно неравенство с одним знаком сравнения.")
    syms = sorted((l - r).free_symbols, key=lambda v: v.name)
    if len(syms) != 1:
        raise UserError("В уравнении должна быть одна неизвестная.")
    if not log_atoms(l - r, syms[0]):
        raise UserError("Неизвестная не стоит под логарифмом. Такую задачу решайте в разделе «Уравнения».")
    if kind == "=":
        return log_equation(w, l, r, syms[0])
    return log_inequality(w, l, kind, r, syms[0])


TOPICS = {
    "logs": solve_logs,
    "derivative": solve_derivative, "integral": solve_integral, "limit": solve_limit,
    "sum": solve_sum, "taylor": solve_taylor, "matrix": solve_matrix,
    "equation": solve_equation, "ode": solve_ode,
}


def solve_json(task_json):
    t = json.loads(task_json)
    try:
        res = TOPICS[t["topic"]](t)
        w = res.pop("work")
        res.update(ok=True, steps=w.steps, tags=w.tags)
    except UserError as e:
        res = {"ok": False, "error": str(e)}
    except Unsolved:
        res = {"ok": False, "error": "Движок не нашёл решения этой задачи. Попробуйте упростить запись или разбить задачу на части."}
    except Exception as e:
        res = {"ok": False, "error": f"Не удалось решить задачу ({type(e).__name__}). Проверьте запись."}
    return json.dumps(res, ensure_ascii=False, default=str)
