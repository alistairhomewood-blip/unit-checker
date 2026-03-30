"""Python source code parser.

Uses the stdlib `ast` module to convert Python source into the
language-independent IR consumed by the constraint builder.

Handles:
    - Variable assignments (simple and augmented)
    - Arithmetic expressions (+, -, *, /, **, //, %)
    - Function definitions with parameters
    - Function calls
    - Return statements
    - Unit annotations from comments (# unit: m/s)
    - Comparison expressions
    - Chained assignments (a = b = expr)
    - Unary operators

Does NOT handle (MVP):
    - Class definitions / methods
    - List comprehensions
    - With statements
    - Try/except
    - Decorators with side effects
    - Dynamic attribute access
    - Import statements
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from unit_checker.core.unit_algebra import UnitVector

from unit_checker.parsers.common.ir import (
    SourceLocation,
    BinaryOperator,
    UnaryOperator,
    ComparisonOperator,
    IRVariable,
    IRExpression,
    IRVariableRef,
    IRLiteral,
    IRBinaryOp,
    IRUnaryOp,
    IRCallExpr,
    IRComparison,
    IRStatement,
    IRAssignment,
    IRReturn,
    IRAugmentedAssignment,
    IRAnnotation,
    IRFunction,
    IRModule,
)

# Regex for unit annotation comments: # unit: <unit_string>
_UNIT_COMMENT_RE = re.compile(r"#\s*unit:\s*(\S+(?:[*/^]\S+)*)", re.MULTILINE)


def parse_python(source: str, file_path: str = "<string>") -> IRModule:
    """Parse Python source code into an IRModule.

    Args:
        source: Python source code string.
        file_path: Path to the source file (for error reporting).

    Returns:
        IRModule with all functions, global statements, and annotations.

    Raises:
        SyntaxError: If the source code has a Python syntax error.
    """
    tree = ast.parse(source, filename=file_path)
    source_lines = source.splitlines()

    parser = _PythonIRBuilder(file_path, source_lines)
    parser.visit_module(tree)
    return parser.module


class _PythonIRBuilder:
    """Walks Python AST and builds IR nodes."""

    def __init__(self, file_path: str, source_lines: list[str]) -> None:
        self.file_path = file_path
        self.source_lines = source_lines
        self.module = IRModule(file_path=file_path)

        # Variable tracking: scope -> name -> IRVariable
        self._variables: dict[str, dict[str, IRVariable]] = {"global": {}}
        self._current_scope = "global"

        # Temporary variable counter for intermediate expressions
        self._temp_counter = 0

    def visit_module(self, node: ast.Module) -> None:
        """Visit the top-level module."""
        # First pass: extract all annotations from comments
        self._extract_comment_annotations()

        # Second pass: process all top-level statements
        for stmt in node.body:
            self._visit_statement(stmt, scope="global")

    def _extract_comment_annotations(self) -> None:
        """Extract unit annotations from comment lines.

        Supported formats:
            variable = value  # unit: m/s
            # unit: m/s   (applies to next assignment)
        """
        for line_num, line in enumerate(self.source_lines, start=1):
            match = _UNIT_COMMENT_RE.search(line)
            if not match:
                continue

            unit_string = match.group(1).strip()
            code_before_comment = line[:match.start()].strip()

            if code_before_comment:
                # Inline comment: variable = value  # unit: m/s
                # Try to extract the variable name from the code before the comment
                var_name = self._extract_var_from_assignment(code_before_comment)
                if var_name:
                    annotation = IRAnnotation(
                        variable_name=var_name,
                        scope="__pending__",  # Will be resolved during statement processing
                        unit_string=unit_string,
                        location=SourceLocation(self.file_path, line_num, match.start() + 1),
                    )
                    self.module.annotations.append(annotation)
            else:
                # Standalone comment: # unit: m/s (applies to next assignment)
                # Look ahead for the next assignment
                for next_line_num in range(line_num, len(self.source_lines)):
                    next_line = self.source_lines[next_line_num].strip()
                    if not next_line or next_line.startswith("#"):
                        continue
                    var_name = self._extract_var_from_assignment(next_line)
                    if var_name:
                        annotation = IRAnnotation(
                            variable_name=var_name,
                            scope="__pending__",
                            unit_string=unit_string,
                            location=SourceLocation(self.file_path, line_num, 1),
                        )
                        self.module.annotations.append(annotation)
                    break

    def _extract_var_from_assignment(self, code: str) -> Optional[str]:
        """Extract variable name from assignment-like code (left side of =)."""
        # Handle "var = expr" or "var: type = expr"
        # Simple approach: split on '=' and take the first token
        if "=" not in code:
            # Check for function parameter: "def f(param" or just a variable name
            # For standalone lines that are just identifiers
            name = code.strip().rstrip(",").strip()
            if name.isidentifier():
                return name
            return None

        parts = code.split("=", 1)
        lhs = parts[0].strip()

        # Handle type annotation: "var: type"
        if ":" in lhs:
            lhs = lhs.split(":")[0].strip()

        # Handle augmented assignment: "var +="
        for op in ("+=", "-=", "*=", "/=", "**=", "//=", "%="):
            if lhs.endswith(op[0]):
                lhs = lhs[:-1].strip()
                break

        if lhs.isidentifier():
            return lhs
        return None

    def _visit_statement(self, node: ast.stmt, scope: str) -> None:
        """Dispatch a statement node to the appropriate handler."""
        old_scope = self._current_scope
        self._current_scope = scope

        if isinstance(node, ast.FunctionDef):
            self._visit_function_def(node)
        elif isinstance(node, ast.Assign):
            stmts = self._visit_assign(node)
            self._add_statements(stmts, scope)
        elif isinstance(node, ast.AugAssign):
            stmt = self._visit_aug_assign(node)
            if stmt:
                self._add_statements([stmt], scope)
        elif isinstance(node, ast.Return):
            stmt = self._visit_return(node)
            if stmt:
                self._add_statements([stmt], scope)
        elif isinstance(node, ast.Expr):
            # Expression statement (e.g., standalone function call)
            # We process it for side effects / function call constraints
            pass
        elif isinstance(node, ast.AnnAssign):
            stmt = self._visit_ann_assign(node)
            if stmt:
                self._add_statements([stmt], scope)
        elif isinstance(node, ast.For):
            # Process the body of for loops
            for body_stmt in node.body:
                self._visit_statement(body_stmt, scope)
        elif isinstance(node, ast.While):
            for body_stmt in node.body:
                self._visit_statement(body_stmt, scope)
        elif isinstance(node, ast.If):
            for body_stmt in node.body:
                self._visit_statement(body_stmt, scope)
            for else_stmt in node.orelse:
                self._visit_statement(else_stmt, scope)

        self._current_scope = old_scope

    def _add_statements(self, stmts: list[IRStatement], scope: str) -> None:
        """Add statements to the appropriate container (function body or module)."""
        if scope == "global":
            self.module.global_statements.extend(stmts)
        # Function body statements are added directly in _visit_function_def

    def _visit_function_def(self, node: ast.FunctionDef) -> None:
        """Convert a function definition to an IRFunction."""
        func_scope = f"local:{node.name}"
        loc = self._loc(node)

        # Create parameter variables
        params: list[IRVariable] = []
        for arg in node.args.args:
            param_scope = f"param:{node.name}"
            param_var = self._get_or_create_var(arg.arg, param_scope, self._loc(arg))
            params.append(param_var)

        # Create synthetic return variable
        return_var = IRVariable(
            name=f"__return_{node.name}__",
            scope=func_scope,
            location=loc,
        )

        # Process function body
        body_stmts: list[IRStatement] = []
        for stmt in node.body:
            old_scope = self._current_scope
            self._current_scope = func_scope
            stmts = self._visit_statement_collect(stmt, func_scope)
            body_stmts.extend(stmts)
            self._current_scope = old_scope

        func = IRFunction(
            name=node.name,
            parameters=params,
            body=body_stmts,
            return_variable=return_var,
            location=loc,
        )
        self.module.functions.append(func)

    def _visit_statement_collect(self, node: ast.stmt, scope: str) -> list[IRStatement]:
        """Process a statement and collect resulting IR statements."""
        results: list[IRStatement] = []

        if isinstance(node, ast.Assign):
            results.extend(self._visit_assign(node))
        elif isinstance(node, ast.AugAssign):
            stmt = self._visit_aug_assign(node)
            if stmt:
                results.append(stmt)
        elif isinstance(node, ast.Return):
            stmt = self._visit_return(node)
            if stmt:
                results.append(stmt)
        elif isinstance(node, ast.AnnAssign):
            stmt = self._visit_ann_assign(node)
            if stmt:
                results.append(stmt)
        elif isinstance(node, ast.Expr):
            # Expression statement -- could be a function call
            pass
        elif isinstance(node, ast.For):
            for body_stmt in node.body:
                results.extend(self._visit_statement_collect(body_stmt, scope))
        elif isinstance(node, ast.While):
            for body_stmt in node.body:
                results.extend(self._visit_statement_collect(body_stmt, scope))
        elif isinstance(node, ast.If):
            for body_stmt in node.body:
                results.extend(self._visit_statement_collect(body_stmt, scope))
            for else_stmt in node.orelse:
                results.extend(self._visit_statement_collect(else_stmt, scope))

        return results

    def _visit_assign(self, node: ast.Assign) -> list[IRStatement]:
        """Convert assignment(s): a = expr, or a = b = expr."""
        stmts: list[IRStatement] = []
        expr = self._visit_expression(node.value)

        for target in node.targets:
            if isinstance(target, ast.Name):
                var = self._get_or_create_var(target.id, self._current_scope, self._loc(target))
                stmts.append(IRAssignment(
                    target=var,
                    expression=expr,
                    location=self._loc(node),
                ))
            elif isinstance(target, ast.Tuple) or isinstance(target, ast.List):
                # Tuple unpacking -- create assignments for each element
                # For now, skip (complex, and not needed for basic physics code)
                pass

        return stmts

    def _visit_ann_assign(self, node: ast.AnnAssign) -> Optional[IRStatement]:
        """Convert annotated assignment: x: int = expr."""
        if node.value is None:
            return None
        if not isinstance(node.target, ast.Name):
            return None

        var = self._get_or_create_var(node.target.id, self._current_scope, self._loc(node.target))
        expr = self._visit_expression(node.value)
        return IRAssignment(
            target=var,
            expression=expr,
            location=self._loc(node),
        )

    def _visit_aug_assign(self, node: ast.AugAssign) -> Optional[IRStatement]:
        """Convert augmented assignment: x += expr."""
        if not isinstance(node.target, ast.Name):
            return None

        op_map = {
            ast.Add: BinaryOperator.ADD,
            ast.Sub: BinaryOperator.SUB,
            ast.Mult: BinaryOperator.MUL,
            ast.Div: BinaryOperator.DIV,
            ast.Pow: BinaryOperator.POW,
            ast.FloorDiv: BinaryOperator.FLOOR_DIV,
            ast.Mod: BinaryOperator.MOD,
        }

        op = op_map.get(type(node.op))
        if op is None:
            return None

        var = self._get_or_create_var(node.target.id, self._current_scope, self._loc(node.target))
        expr = self._visit_expression(node.value)
        return IRAugmentedAssignment(
            target=var,
            operator=op,
            expression=expr,
            location=self._loc(node),
        )

    def _visit_return(self, node: ast.Return) -> Optional[IRStatement]:
        """Convert return statement."""
        if node.value is None:
            return None

        expr = self._visit_expression(node.value)
        return IRReturn(
            expression=expr,
            location=self._loc(node),
        )

    def _visit_expression(self, node: ast.expr) -> IRExpression:
        """Convert an expression AST node to IR."""
        loc = self._loc(node)

        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return IRLiteral(value=float(node.value), location=loc)
            # String or other constant -- treat as dimensionless literal
            return IRLiteral(value=0.0, location=loc)

        if isinstance(node, ast.Name):
            var = self._get_or_create_var(node.id, self._current_scope, loc)
            return IRVariableRef(variable=var, location=loc)

        if isinstance(node, ast.BinOp):
            return self._visit_binop(node)

        if isinstance(node, ast.UnaryOp):
            return self._visit_unaryop(node)

        if isinstance(node, ast.Call):
            return self._visit_call(node)

        if isinstance(node, ast.Compare):
            return self._visit_compare(node)

        if isinstance(node, ast.Attribute):
            # e.g., math.sqrt -- treat as a call if parent is Call, otherwise unknown
            # For MVP, treat attribute access as producing an unknown variable
            attr_name = f"__attr_{ast.dump(node)}__"
            var = self._get_or_create_var(attr_name, self._current_scope, loc)
            return IRVariableRef(variable=var, location=loc)

        if isinstance(node, ast.Subscript):
            # e.g., array[i] -- for MVP, treat same unit as the array
            return self._visit_expression(node.value)

        if isinstance(node, ast.IfExp):
            # Ternary: x if cond else y -- both branches should have same unit
            # For MVP, just use the body (true branch)
            return self._visit_expression(node.body)

        # Fallback: unknown expression -> dimensionless literal
        return IRLiteral(value=0.0, location=loc)

    def _visit_binop(self, node: ast.BinOp) -> IRExpression:
        """Convert binary operation."""
        loc = self._loc(node)
        left = self._visit_expression(node.left)
        right = self._visit_expression(node.right)

        op_map = {
            ast.Add: BinaryOperator.ADD,
            ast.Sub: BinaryOperator.SUB,
            ast.Mult: BinaryOperator.MUL,
            ast.Div: BinaryOperator.DIV,
            ast.Pow: BinaryOperator.POW,
            ast.FloorDiv: BinaryOperator.FLOOR_DIV,
            ast.Mod: BinaryOperator.MOD,
        }

        op = op_map.get(type(node.op))
        if op is None:
            # Unknown operator -- return left operand as approximation
            return left

        return IRBinaryOp(operator=op, left=left, right=right, location=loc)

    def _visit_unaryop(self, node: ast.UnaryOp) -> IRExpression:
        """Convert unary operation."""
        loc = self._loc(node)
        operand = self._visit_expression(node.operand)

        if isinstance(node.op, ast.USub):
            return IRUnaryOp(operator=UnaryOperator.NEG, operand=operand, location=loc)
        elif isinstance(node.op, ast.UAdd):
            return IRUnaryOp(operator=UnaryOperator.POS, operand=operand, location=loc)

        # For other unary ops (Not, Invert), return operand
        return operand

    def _visit_call(self, node: ast.Call) -> IRExpression:
        """Convert function call."""
        loc = self._loc(node)

        # Get function name
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            # e.g., math.sqrt -> "math.sqrt"
            parts: list[str] = []
            n: ast.expr = node.func
            while isinstance(n, ast.Attribute):
                parts.append(n.attr)
                n = n.value
            if isinstance(n, ast.Name):
                parts.append(n.id)
            func_name = ".".join(reversed(parts))
        else:
            func_name = "__unknown_func__"

        args = [self._visit_expression(arg) for arg in node.args]

        return IRCallExpr(
            function_name=func_name,
            arguments=args,
            location=loc,
        )

    def _visit_compare(self, node: ast.Compare) -> IRExpression:
        """Convert comparison expression."""
        loc = self._loc(node)
        left = self._visit_expression(node.left)

        # For simplicity, handle only the first comparator
        if node.comparators:
            right = self._visit_expression(node.comparators[0])
            op_map = {
                ast.Eq: ComparisonOperator.EQ,
                ast.NotEq: ComparisonOperator.NE,
                ast.Lt: ComparisonOperator.LT,
                ast.LtE: ComparisonOperator.LE,
                ast.Gt: ComparisonOperator.GT,
                ast.GtE: ComparisonOperator.GE,
            }
            op = op_map.get(type(node.ops[0]))
            if op:
                return IRComparison(operator=op, left=left, right=right, location=loc)

        return left

    def _get_or_create_var(self, name: str, scope: str, location: SourceLocation) -> IRVariable:
        """Get an existing variable or create a new one in the given scope.

        Variables are deduplicated by (scope, name). When inside a function
        body (local:func scope), also checks if the variable is a parameter
        (param:func scope) before creating a new local variable.
        """
        scope_vars = self._variables.setdefault(scope, {})

        if name in scope_vars:
            return scope_vars[name]

        # If we're in a local function scope, check if this is a parameter
        if scope.startswith("local:"):
            func_name = scope[6:]
            param_scope = f"param:{func_name}"
            param_vars = self._variables.get(param_scope, {})
            if name in param_vars:
                # Reuse the parameter variable -- don't create a new local
                scope_vars[name] = param_vars[name]
                return param_vars[name]

        # Create a new variable
        annotation = self._find_annotation(name, scope)
        var = IRVariable(
            name=name,
            scope=scope,
            location=location,
            annotation=annotation,
        )
        scope_vars[name] = var
        return var

    def _find_annotation(self, var_name: str, scope: str) -> Optional[UnitVector]:
        """Find annotation for a variable. Annotations are resolved later by the constraint builder."""
        # Annotations are stored in module.annotations and resolved during constraint building
        # We don't resolve them here because the registry hasn't been applied yet
        return None

    def _loc(self, node: ast.AST) -> SourceLocation:
        """Extract source location from an AST node."""
        line = getattr(node, "lineno", 0)
        col = getattr(node, "col_offset", 0)
        return SourceLocation(self.file_path, line, col)

    def _next_temp_name(self) -> str:
        """Generate a unique temporary variable name."""
        self._temp_counter += 1
        return f"__temp_{self._temp_counter}__"
