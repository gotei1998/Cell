"""Проверки решателя: запускаются командой `python -m pytest tests`."""
import json

import pytest
import sympy as sp

import solver


def run(**task):
    return json.loads(solver.solve_json(json.dumps(task)))


def answer(**task):
    r = run(**task)
    assert r["ok"], r.get("error")
    return r


def error(**task):
    r = run(**task)
    assert not r["ok"], r.get("answer")
    return r["error"]


# ---------- Разбор записи ----------

@pytest.mark.parametrize("text, expected", [
    ("x^2*sin(x)", "x**2*sin(x)"),
    ("2sinx cosx", "2*sin(x)*cos(x)"),
    ("sin x cos x", "sin(x)*cos(x)"),
    ("sin 2x cos x", "sin(2*x)*cos(x)"),
    ("sin^2 x cos x", "sin(x)**2*cos(x)"),
    ("sin x^2", "sin(x**2)"),
    ("sin x / x", "sin(x)/x"),
    ("x^2 sin x", "x**2*sin(x)"),
    ("ln x + lg x", "log(x) + log(x)/log(10)"),
    ("sqrt x", "sqrt(x)"),
    ("sin(x)cos(x)", "sin(x)*cos(x)"),
    ("sin(2x)", "sin(2*x)"),
    ("sin xy", "sin(x*y)"),
    ("xe^x", "x*exp(x)"),
    ("e^(2x)", "exp(2*x)"),
    ("arctg x", "atan(x)"),
    ("tg(x) + ctg(x)", "tan(x) + cot(x)"),
    ("sh(x)*ch(x)", "sinh(x)*cosh(x)"),
    ("cosec(x)", "csc(x)"),
    ("ln(x+1)", "log(x + 1)"),
    ("lg(100)", "2"),
    ("log_2(8)", "3"),
    ("√x", "sqrt(x)"),
    ("x²+x³", "x**2 + x**3"),
    ("2,5x", "5*x/2"),
    ("х^2", "x**2"),  # кириллическая «х»
    ("π", "pi"),
    ("|x|", "Abs(x)"),
    ("||x|-1|", "Abs(Abs(x) - 1)"),
    ("2|x-1|", "2*Abs(x - 1)"),
    ("x*|x|+|y|", "x*Abs(x) + Abs(y)"),
    ("n!", "factorial(n)"),
    ("(n+1)!/n!", "factorial(n + 1)/factorial(n)"),
    ("3!", "6"),
    ("бесконечность", "oo"),
    ("-Бесконечность", "-oo"),
    ("∞", "oo"),
    ("inf", "oo"),
])
def test_parse(text, expected):
    assert solver.parse(text) == sp.sympify(expected)


@pytest.mark.parametrize("text, part", [
    ("корень из x", "русские буквы"),
    ("синус(x)", "русские буквы"),
    ("[x]", "недопустимый символ"),
    ("x; y", "недопустимый символ"),
    ("\\sin x", "недопустимый символ"),
    ("|x", "недопустимый символ"),
    ("y = x^2", "недопустимый символ"),
    ("x +", "Не удалось разобрать"),
    ("", "Заполните поле"),
])
def test_parse_rejects(text, part):
    with pytest.raises(solver.UserError, match=part):
        solver.parse(text)


@pytest.mark.parametrize("text", [
    '__import__("os").getcwd()',
    "x.__class__",
    "x.real",
    "().__class__",
    "lambda: 1",
    "'a'*3",
])
def test_parse_blocks_code(text):
    with pytest.raises(solver.UserError):
        solver.parse(text)


@pytest.mark.parametrize("name", ["open", "exec", "eval", "getattr", "chr", "print", "sympify", "__import__"])
def test_parse_has_no_python_builtins(name):
    assert name not in solver.SAFE_GLOBALS
    assert solver.SAFE_GLOBALS["__builtins__"] == {}


# ---------- Производные ----------

@pytest.mark.parametrize("f, order, expected", [
    ("x^2*sin(x)", "1", "x**2*cos(x) + 2*x*sin(x)"),
    ("ln(x^2+1)/x", "1", "2/(x**2+1) - log(x**2+1)/x**2"),
    ("x^x", "1", "x**x*(log(x)+1)"),
    ("arctg(e^(2x))", "2", "diff(atan(exp(2*x)), x, 2)"),
    ("sin(x)", "10", "-sin(x)"),
    ("a*x^3+b", "3", "6*a"),
    ("sqrt(-x-5)", "1", "-1/(2*sqrt(-x-5))"),
    ("x!", "1", "gamma(x+1)*polygamma(0, x+1)"),
])
def test_derivative(f, order, expected):
    r = answer(topic="derivative", f=f, var="x", order=order)
    assert r["check"] and r["check"]["ok"]
    got = sp.diff(solver.parse(f), sp.Symbol("x"), int(order))
    assert sp.simplify(got - sp.sympify(expected)) == 0
    assert r["steps"]


def test_derivative_of_modulus():
    r = answer(topic="derivative", f="|x|", var="x")
    assert r["answer"].endswith(r"\operatorname{sign}{\left(x \right)}")
    assert r["check"]["ok"] and "модул" in r["note"]
    r = answer(topic="derivative", f="|x^2-1|", var="x", order="2")
    assert "delta" not in r["answer"] and r["check"]["ok"]


@pytest.mark.parametrize("order", ["abc", "0", "11", "2.5", "-1"])
def test_derivative_bad_order(order):
    assert "целое число от 1 до 10" in error(topic="derivative", f="x^2", var="x", order=order)


def test_derivative_check_is_independent():
    x = sp.Symbol("x")
    f = x**2 * sp.sin(x)
    assert solver.check_derivative(f, sp.diff(f, x), x, 1)["ok"]
    assert not solver.check_derivative(f, x**2 * sp.cos(x), x, 1)["ok"]
    assert not solver.check_derivative(sp.sin(x), sp.cos(x) * (1 + sp.Rational(1, 10**6)), x, 1)["ok"]
    assert solver.check_derivative(x**x, sp.diff(x**x, x, 10), x, 10)["ok"]


def test_check_numeric_needs_a_point():
    x = sp.Symbol("x")
    assert solver.check_numeric(sp.zoo + 0 * x, x, "t") is None
    assert solver.check_numeric(sp.Integer(0), x, "t")["ok"]
    assert not solver.check_numeric(x - x**2, x, "t")["ok"]


# ---------- Интегралы ----------

@pytest.mark.parametrize("f", [
    "x^2*e^x", "1/(x^2+4x+5)", "x*cos(x)", "e^x*sin(x)", "1/(x^2-1)", "1/x", "sin(x)^2", "tg(x)", "|x|",
])
def test_antiderivative(f):
    r = answer(topic="integral", f=f, var="x", a="", b="")
    assert r["check"]["ok"]
    assert r["answer"].endswith("+ C")


@pytest.mark.parametrize("f, a, b, expected", [
    ("sin(x)^2", "0", "pi", "pi/2"),
    ("x^2", "0", "3", "9"),
    ("x^2", "3", "0", "-9"),
    ("1/x", "1", "e", "1"),
    ("1/sqrt(x)", "0", "1", "2"),
    ("ln(x)", "0", "1", "-1"),
    ("1/x^2", "1", "oo", "1"),
    ("e^(-x^2)", "-oo", "oo", "sqrt(pi)"),
    ("1/sqrt(1-x^2)", "-1", "1", "pi"),
    ("|x|", "-1", "2", "5/2"),
    ("|x-1|", "0", "3", "5/2"),
])
def test_definite_integral(f, a, b, expected):
    r = answer(topic="integral", f=f, var="x", a=a, b=b)
    x = sp.Symbol("x", real=True)
    val, _ = solver.definite(solver.parse(f).subs(sp.Symbol("x"), x), x, solver.parse(a), solver.parse(b))
    assert sp.simplify(val - sp.sympify(expected)) == 0
    assert "расходится" not in r["answer"]


@pytest.mark.parametrize("f, a, b", [
    ("1/x", "-1", "1"),
    ("1/x", "1", "-1"),
    ("1/x^2", "-1", "1"),
    ("1/x^3", "-1", "1"),
    ("1/(x-1)", "0", "2"),
    ("1/(x-1)^2", "0", "2"),
    ("1/(x^2-1)", "0", "3"),
    ("tg(x)", "0", "pi"),
    ("1/sin(x)", "0", "pi"),
    ("1/x", "0", "1"),
    ("1/x", "1", "oo"),
    ("sin(x)", "0", "oo"),
])
def test_divergent_integral(f, a, b):
    r = answer(topic="integral", f=f, var="x", a=a, b=b)
    assert r["answer"].endswith(r"\text{ расходится}")
    assert "NaN" not in r["answer"] and r"\infty}" not in r["answer"].split("dx")[-1]
    assert r["check"] is None


def test_integral_needs_both_limits():
    assert "оба предела" in error(topic="integral", f="x^2", var="x", a="0", b="")


def test_nonelementary_integral():
    r = answer(topic="integral", f="sin(x)/x", var="x", a="", b="")
    assert "специальную функцию" in r["note"]


# ---------- Пределы ----------

@pytest.mark.parametrize("f, point, side, expected", [
    ("(1-cos(x))/x^2", "0", "+-", r"\frac{1}{2}"),
    ("(1+1/x)^x", "oo", "+-", "e"),
    ("(1+1/x)^x", "бесконечность", "+-", "e"),
    ("ln(x)/x", "oo", "+-", "0"),
    ("sin(x)/x", "0", "-", "1"),
    ("1/x", "0", "+", r"\infty"),
    ("|x|/x", "0", "+", "1"),
    ("|x|/x", "0", "-", "-1"),
])
def test_limit(f, point, side, expected):
    r = answer(topic="limit", f=f, var="x", point=point, side=side)
    assert r["answer"].endswith("= " + expected)


@pytest.mark.parametrize("f", ["1/x", "|x|/x"])
def test_limit_does_not_exist(f):
    r = answer(topic="limit", f=f, var="x", point="0", side="+-")
    assert r["answer"].endswith(r"\text{ не существует}")


# ---------- Ряды ----------

@pytest.mark.parametrize("f, var, a, b, expected", [
    ("1/n^2", "n", "1", "oo", r"\frac{\pi^{2}}{6}"),
    ("n/2^n", "n", "1", "oo", "2"),
    ("k^2", "k", "1", "10", "385"),
    ("1/n!", "n", "0", "oo", "e"),
])
def test_sum(f, var, a, b, expected):
    r = answer(topic="sum", f=f, var=var, a=a, b=b)
    assert r["answer"].endswith("= " + expected)
    assert r["check"]["ok"]


def test_sum_diverges():
    assert answer(topic="sum", f="1/n", var="n", a="1", b="oo")["answer"].endswith(r"\text{ расходится}")


def test_taylor():
    r = answer(topic="taylor", f="e^x*cos(x)", var="x", point="0", order="5")
    assert r["check"]["ok"] and r["steps"]
    assert "целое число от 1 до 20" in error(topic="taylor", f="e^x", var="x", point="0", order="x")


# ---------- Логарифмы ----------

@pytest.mark.parametrize("f, expected", [
    ("log_2(x-1) + log_2(x+1) = 3", "x = 3"),
    ("lg(25) + lg(4)", "= 2"),
    ("lg(x)^2 - 3lg(x) + 2 = 0", "x = 10, x = 100"),
    ("log_x(8) = 3", "x = 2"),
    ("log_(1/2)(x-1) > -2", r"x \in \left(1, 5\right)"),
])
def test_logs(f, expected):
    r = answer(topic="logs", f=f)
    assert r["answer"].endswith(expected)
    assert r["check"]["ok"]


# ---------- Матрицы ----------

def test_matrix():
    assert answer(topic="matrix", matrix="2 1 3\n1 0 2\n4 1 8", op="det")["answer"] == r"\det A = -1"
    assert answer(topic="matrix", matrix="1 2\n3 4", op="inv")["check"]["ok"]
    assert answer(topic="matrix", matrix="1 2 3\n2 4 6", op="rank")["answer"].endswith("= 1")
    assert answer(topic="matrix", matrix="2 0\n1 3", op="eigen")["check"]["ok"]
    assert "нет" in answer(topic="matrix", matrix="1 2\n2 4", op="inv")["answer"]


def test_matrix_rejects():
    assert "квадратной" in error(topic="matrix", matrix="1 2 3\n2 4 6", op="det")
    assert "разное число" in error(topic="matrix", matrix="1 2\n3", op="det")
    assert "конечными" in error(topic="matrix", matrix="1 2\n3 oo", op="det")
    assert "русские буквы" in error(topic="matrix", matrix="1 2\n3 много", op="det")


# ---------- Уравнения ----------

@pytest.mark.parametrize("f, expected", [
    ("x^3 - 6x^2 + 11x - 6 = 0", "x_{1} = 1, x_{2} = 2, x_{3} = 3"),
    ("x^2 = 4", "x_{1} = -2, x_{2} = 2"),
    ("|x-1| = 2", "x_{1} = -1, x_{2} = 3"),
    ("x + 2y - z = 3\n2x - y + z = 1\nx + y + z = 6", r"x = \frac{3}{7},\quad y = \frac{19}{7},\quad z = \frac{20}{7}"),
])
def test_equation(f, expected):
    r = answer(topic="equation", f=f)
    assert r["answer"] == expected
    assert r["check"]["ok"]


def test_equation_without_real_roots():
    assert "Действительных корней нет" in answer(topic="equation", f="x^2+1=0")["answer"]


# ---------- Дифференциальные уравнения ----------

@pytest.mark.parametrize("f, ics", [
    ("y'' + 2y' + y = sin(x)", ""),
    ("y' = x*y", "y(0)=1"),
    ("y' + y/x = x^2", ""),
    ("y'' + 4y = 0", "y(0)=1, y'(0)=0"),
])
def test_ode(f, ics):
    assert answer(topic="ode", f=f, ics=ics)["check"]["ok"]


# ---------- Общее ----------

def test_unsupported_problem_has_clear_message():
    assert "не нашёл решения" in error(topic="sum", f="x^n/n!", var="n", a="0", b="oo")


def test_plot_follows_the_problem():
    pts = answer(topic="integral", f="x", var="x", a="0", b="2")["plot"][0]["points"]
    assert (pts[0][0], pts[-1][0]) == (-6.0, 6.0)
    pts = answer(topic="integral", f="x", var="x", a="0", b="100")["plot"][0]["points"]
    assert pts[0][0] < 0 and pts[-1][0] > 100
    pts = answer(topic="limit", f="1/(x-100)", var="x", point="100", side="+")["plot"][0]["points"]
    assert pts[0][0] < 100 < pts[-1][0]
