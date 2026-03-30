"""Intermediate Representation (IR) definitions.

Language-independent representation of source code, consumed by the
constraint builder and inference engine. Every language parser produces
IR; the inference engine never sees language-specific AST nodes.

Node types:
    IRModule        -- top-level container for a single file
    IRFunction      -- function/subroutine definition
    IRVariable      -- a named quantity (with scope tracking)
    IRAssignment    -- target = expression
    IRReturn        -- return expression
    IRExpression    -- arithmetic/logic expression tree
    IRAnnotation    -- user-provided unit annotation

Expression types:
    IRVariableRef   -- reference to a variable
    IRLiteral       -- numeric literal
    IRBinaryOp      -- binary operation (+, -, *, /, **)
    IRUnaryOp       -- unary operation (-, +)
    IRCallExpr      -- function call expression
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from unit_checker.core.unit_algebra import UnitVector


# --- Source Location ---

@dataclass(frozen=True, slots=True)
class SourceLocation:
    """Location in source code for error reporting."""
    file: str
    line: int
    column: int

    def __str__(self) -> str:
        return f"{self.file}:{self.line}:{self.column}"


# --- Operators ---

class BinaryOperator(Enum):
    """Binary operators that affect unit propagation."""
    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"
    POW = "**"
    FLOOR_DIV = "//"
    MOD = "%"


class UnaryOperator(Enum):
    """Unary operators."""
    POS = "+"
    NEG = "-"


class ComparisonOperator(Enum):
    """Comparison operators (require same units, produce boolean)."""
    EQ = "=="
    NE = "!="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="


# --- Variables ---

@dataclass
class IRVariable:
    """A named quantity in the source code.

    Attributes:
        name: Variable name as it appears in source.
        scope: Scope identifier (e.g., "global", "local:func_name", "param:func_name").
        location: Where the variable is first defined/used.
        annotation: User-provided unit, if any.
    """
    name: str
    scope: str
    location: SourceLocation
    annotation: Optional[UnitVector] = None

    @property
    def qualified_name(self) -> str:
        """Fully qualified name for constraint graph (scope::name)."""
        return f"{self.scope}::{self.name}"

    def __hash__(self) -> int:
        return hash(self.qualified_name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, IRVariable):
            return NotImplemented
        return self.qualified_name == other.qualified_name


# --- Expressions ---

@dataclass
class IRExpression:
    """Base class for all expressions."""
    location: SourceLocation


@dataclass
class IRVariableRef(IRExpression):
    """Reference to a variable."""
    variable: IRVariable


@dataclass
class IRLiteral(IRExpression):
    """Numeric literal value."""
    value: float


@dataclass
class IRBinaryOp(IRExpression):
    """Binary operation (e.g., a + b, x * y, z ** 2)."""
    operator: BinaryOperator
    left: IRExpression
    right: IRExpression


@dataclass
class IRUnaryOp(IRExpression):
    """Unary operation (e.g., -x, +x)."""
    operator: UnaryOperator
    operand: IRExpression


@dataclass
class IRCallExpr(IRExpression):
    """Function call expression (e.g., f(a, b))."""
    function_name: str
    arguments: list[IRExpression]


@dataclass
class IRComparison(IRExpression):
    """Comparison expression (e.g., a < b). Result is boolean (no unit)."""
    operator: ComparisonOperator
    left: IRExpression
    right: IRExpression


# --- Statements ---

@dataclass
class IRStatement:
    """Base class for all statements."""
    location: SourceLocation


@dataclass
class IRAssignment(IRStatement):
    """Assignment: target = expression."""
    target: IRVariable
    expression: IRExpression


@dataclass
class IRReturn(IRStatement):
    """Return statement: return expression."""
    expression: IRExpression


@dataclass
class IRAugmentedAssignment(IRStatement):
    """Augmented assignment: target += expression, target *= expression, etc."""
    target: IRVariable
    operator: BinaryOperator
    expression: IRExpression


# --- Annotations ---

@dataclass(frozen=True)
class IRAnnotation:
    """User-provided unit annotation from comments, type hints, or decorators.

    This is the raw annotation as found in the source code, before the
    unit string is parsed into a UnitVector.
    """
    variable_name: str
    scope: str
    unit_string: str
    location: SourceLocation


# --- Functions ---

@dataclass
class IRFunction:
    """Function definition.

    Attributes:
        name: Function name.
        parameters: Ordered list of parameter variables.
        body: List of statements in the function body.
        return_variable: Synthetic variable representing the return value.
        location: Source location of the function definition.
    """
    name: str
    parameters: list[IRVariable]
    body: list[IRStatement]
    return_variable: Optional[IRVariable]
    location: SourceLocation


# --- Module (top-level container) ---

@dataclass
class IRModule:
    """Top-level IR container for a single source file.

    Attributes:
        file_path: Path to the source file.
        functions: All function definitions.
        global_statements: Top-level statements (assignments, expressions).
        annotations: All unit annotations found in the file.
    """
    file_path: str
    functions: list[IRFunction] = field(default_factory=list)
    global_statements: list[IRStatement] = field(default_factory=list)
    annotations: list[IRAnnotation] = field(default_factory=list)
