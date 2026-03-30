"""Tests for the Python parser (Checkpoint 2).

Tests cover:
    2.1  Simple assignment
    2.2  Arithmetic expression
    2.3  Function definition
    2.4  Function call
    2.5  Comment annotation
    2.6  Nested expressions
    2.7  Chained assignment
    2.8  Return statement
    2.9  Source locations
    2.10 Multiple functions
"""


from unit_checker.parsers.python_parser.parser import parse_python
from unit_checker.parsers.common.ir import (
    IRAssignment,
    IRReturn,
    IRLiteral,
    IRBinaryOp,
    IRCallExpr,
    IRVariableRef,
    BinaryOperator,
)


class TestSimpleAssignment:
    """2.1: x = 5.0 produces IRAssignment with IRLiteral."""

    def test_simple_numeric_assignment(self):
        module = parse_python("x = 5.0", "test.py")
        assert len(module.global_statements) == 1
        stmt = module.global_statements[0]
        assert isinstance(stmt, IRAssignment)
        assert stmt.target.name == "x"
        assert isinstance(stmt.expression, IRLiteral)
        assert stmt.expression.value == 5.0

    def test_integer_assignment(self):
        module = parse_python("x = 42", "test.py")
        stmt = module.global_statements[0]
        assert isinstance(stmt, IRAssignment)
        assert isinstance(stmt.expression, IRLiteral)
        assert stmt.expression.value == 42.0


class TestArithmeticExpression:
    """2.2: y = a + b * c produces correct IR tree with precedence."""

    def test_add_mul_precedence(self):
        source = "a = 1\nb = 2\nc = 3\ny = a + b * c"
        module = parse_python(source, "test.py")
        # Last statement should be y = a + b * c
        stmt = module.global_statements[-1]
        assert isinstance(stmt, IRAssignment)
        assert stmt.target.name == "y"
        expr = stmt.expression
        assert isinstance(expr, IRBinaryOp)
        assert expr.operator == BinaryOperator.ADD
        # Left is 'a' reference
        assert isinstance(expr.left, IRVariableRef)
        assert expr.left.variable.name == "a"
        # Right is 'b * c'
        assert isinstance(expr.right, IRBinaryOp)
        assert expr.right.operator == BinaryOperator.MUL

    def test_subtraction(self):
        module = parse_python("x = 1\ny = 2\nz = x - y", "test.py")
        stmt = module.global_statements[-1]
        expr = stmt.expression
        assert isinstance(expr, IRBinaryOp)
        assert expr.operator == BinaryOperator.SUB

    def test_division(self):
        module = parse_python("x = 1\ny = 2\nz = x / y", "test.py")
        stmt = module.global_statements[-1]
        expr = stmt.expression
        assert isinstance(expr, IRBinaryOp)
        assert expr.operator == BinaryOperator.DIV

    def test_power(self):
        module = parse_python("x = 1\ny = x ** 2", "test.py")
        stmt = module.global_statements[-1]
        expr = stmt.expression
        assert isinstance(expr, IRBinaryOp)
        assert expr.operator == BinaryOperator.POW


class TestFunctionDefinition:
    """2.3: def f(x, y): return x + y produces IRFunction."""

    def test_simple_function(self):
        source = "def f(x, y):\n    return x + y"
        module = parse_python(source, "test.py")
        assert len(module.functions) == 1
        func = module.functions[0]
        assert func.name == "f"
        assert len(func.parameters) == 2
        assert func.parameters[0].name == "x"
        assert func.parameters[1].name == "y"
        assert func.return_variable is not None

    def test_function_body_has_return(self):
        source = "def f(x):\n    return x * 2"
        module = parse_python(source, "test.py")
        func = module.functions[0]
        assert len(func.body) == 1
        assert isinstance(func.body[0], IRReturn)


class TestFunctionCall:
    """2.4: z = f(a, b) produces IRCallExpr."""

    def test_simple_call(self):
        source = "def f(x, y):\n    return x + y\nz = f(1, 2)"
        module = parse_python(source, "test.py")
        # Global statement should be the assignment z = f(1, 2)
        assert len(module.global_statements) == 1
        stmt = module.global_statements[0]
        assert isinstance(stmt, IRAssignment)
        assert stmt.target.name == "z"
        expr = stmt.expression
        assert isinstance(expr, IRCallExpr)
        assert expr.function_name == "f"
        assert len(expr.arguments) == 2


class TestCommentAnnotation:
    """2.5: # unit: m/s produces IRAnnotation."""

    def test_inline_annotation(self):
        source = "velocity = 10.0  # unit: m/s"
        module = parse_python(source, "test.py")
        assert len(module.annotations) == 1
        ann = module.annotations[0]
        assert ann.variable_name == "velocity"
        assert ann.unit_string == "m/s"

    def test_multiple_annotations(self):
        source = "v = 10.0  # unit: m/s\na = 9.8  # unit: m/s^2"
        module = parse_python(source, "test.py")
        assert len(module.annotations) == 2
        assert module.annotations[0].unit_string == "m/s"
        assert module.annotations[1].unit_string == "m/s^2"

    def test_annotation_with_named_unit(self):
        source = "force = 100.0  # unit: N"
        module = parse_python(source, "test.py")
        assert len(module.annotations) == 1
        assert module.annotations[0].unit_string == "N"


class TestNestedExpressions:
    """2.6: z = (a + b) * (c - d) produces correct IR tree."""

    def test_nested_groups(self):
        source = "a = 1\nb = 2\nc = 3\nd = 4\nz = (a + b) * (c - d)"
        module = parse_python(source, "test.py")
        stmt = module.global_statements[-1]
        expr = stmt.expression
        assert isinstance(expr, IRBinaryOp)
        assert expr.operator == BinaryOperator.MUL
        assert isinstance(expr.left, IRBinaryOp)
        assert expr.left.operator == BinaryOperator.ADD
        assert isinstance(expr.right, IRBinaryOp)
        assert expr.right.operator == BinaryOperator.SUB


class TestChainedAssignment:
    """2.7: a = b = 5.0 produces multiple IRAssignments."""

    def test_chained_assign(self):
        source = "a = b = 5.0"
        module = parse_python(source, "test.py")
        # Should produce 2 assignments: one for a, one for b
        assert len(module.global_statements) == 2
        names = {s.target.name for s in module.global_statements}
        assert "a" in names
        assert "b" in names


class TestReturnStatement:
    """2.8: return x * y produces IRReturn."""

    def test_return_expression(self):
        source = "def f(x, y):\n    return x * y"
        module = parse_python(source, "test.py")
        func = module.functions[0]
        ret = func.body[0]
        assert isinstance(ret, IRReturn)
        assert isinstance(ret.expression, IRBinaryOp)
        assert ret.expression.operator == BinaryOperator.MUL


class TestSourceLocations:
    """2.9: All IR nodes have correct file/line/column."""

    def test_assignment_location(self):
        source = "x = 5.0"
        module = parse_python(source, "test.py")
        stmt = module.global_statements[0]
        assert stmt.location.file == "test.py"
        assert stmt.location.line == 1

    def test_function_location(self):
        source = "\n\ndef my_func():\n    return 1"
        module = parse_python(source, "test.py")
        func = module.functions[0]
        assert func.location.line == 3

    def test_multi_line_locations(self):
        source = "a = 1\nb = 2\nc = a + b"
        module = parse_python(source, "test.py")
        assert module.global_statements[0].location.line == 1
        assert module.global_statements[1].location.line == 2
        assert module.global_statements[2].location.line == 3


class TestMultipleFunctions:
    """2.10: File with 3 functions produces 3 IRFunction nodes."""

    def test_three_functions(self):
        source = """
def f1(x):
    return x

def f2(x, y):
    return x + y

def f3(x, y, z):
    return x * y * z
"""
        module = parse_python(source, "test.py")
        assert len(module.functions) == 3
        assert module.functions[0].name == "f1"
        assert module.functions[1].name == "f2"
        assert module.functions[2].name == "f3"
        assert len(module.functions[0].parameters) == 1
        assert len(module.functions[1].parameters) == 2
        assert len(module.functions[2].parameters) == 3
