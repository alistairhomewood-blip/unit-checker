"""Fortran source code parser using tree-sitter.

Uses the tree-sitter-fortran grammar to convert Fortran source into the
language-independent IR consumed by the constraint builder.

Handles:
    - Variable declarations (real, integer, double precision, etc.)
    - Arithmetic expressions (+, -, *, /, **)
    - Function definitions with parameters and result variables
    - Subroutine definitions with parameters
    - Function/intrinsic calls (sqrt, abs, etc.)
    - Assignment statements
    - Unit annotations from comments (! unit: m/s)
    - Unary operators (-, +)
    - Program blocks, module blocks

Does NOT handle (MVP):
    - COMMON blocks
    - EQUIVALENCE statements
    - Array operations / slicing
    - WHERE / FORALL constructs
    - Derived types / structures
    - Interface blocks
    - USE statements / module imports
    - IMPLICIT typing (assumes IMPLICIT NONE)
    - Fixed-form Fortran (F77)
    - DO CONCURRENT
    - SELECT CASE
    - Associate blocks
"""

from __future__ import annotations

import re
from typing import Optional

import tree_sitter_fortran as tsfortran
import tree_sitter as ts

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
    IRAnnotation,
    IRFunction,
    IRModule,
)

# Regex for unit annotations in Fortran comments: ! unit: <unit_string>
_FORTRAN_UNIT_RE = re.compile(r"!\s*unit:\s*(\S+(?:[*/^]\S+)*)")

# Fortran binary operators -> IR operators
_BINOP_MAP: dict[str, BinaryOperator] = {
    "+": BinaryOperator.ADD,
    "-": BinaryOperator.SUB,
    "*": BinaryOperator.MUL,
    "/": BinaryOperator.DIV,
    "**": BinaryOperator.POW,
}

# Fortran comparison operators -> IR operators
_CMP_MAP: dict[str, ComparisonOperator] = {
    "==": ComparisonOperator.EQ,
    "/=": ComparisonOperator.NE,
    "<": ComparisonOperator.LT,
    "<=": ComparisonOperator.LE,
    ">": ComparisonOperator.GT,
    ">=": ComparisonOperator.GE,
    ".eq.": ComparisonOperator.EQ,
    ".ne.": ComparisonOperator.NE,
    ".lt.": ComparisonOperator.LT,
    ".le.": ComparisonOperator.LE,
    ".gt.": ComparisonOperator.GT,
    ".ge.": ComparisonOperator.GE,
}

# Lazy-initialised parser and language
_ts_language: Optional[ts.Language] = None
_ts_parser: Optional[ts.Parser] = None


def _get_parser() -> ts.Parser:
    """Return (and lazily initialise) the tree-sitter Fortran parser."""
    global _ts_language, _ts_parser
    if _ts_parser is None:
        _ts_language = ts.Language(tsfortran.language())
        _ts_parser = ts.Parser(_ts_language)
    return _ts_parser


def parse_fortran(source: str, file_path: str = "<string>") -> IRModule:
    """Parse Fortran source code into an IRModule.

    Args:
        source: Fortran source code string.
        file_path: Path to the source file (for error reporting).

    Returns:
        IRModule with all functions, global statements, and annotations.
    """
    parser = _get_parser()
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)

    builder = _FortranIRBuilder(file_path, source, source_bytes, tree)
    builder.build()
    return builder.module


class _FortranIRBuilder:
    """Walks the tree-sitter Fortran AST and builds IR nodes."""

    def __init__(
        self,
        file_path: str,
        source: str,
        source_bytes: bytes,
        tree: ts.Tree,
    ) -> None:
        self.file_path = file_path
        self.source = source
        self.source_bytes = source_bytes
        self.source_lines = source.splitlines()
        self.tree = tree
        self.module = IRModule(file_path=file_path)

        # Variable tracking: scope -> name -> IRVariable
        self._variables: dict[str, dict[str, IRVariable]] = {"global": {}}
        self._current_scope = "global"

        # Temporary variable counter
        self._temp_counter = 0

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def build(self) -> None:
        """Process the entire translation unit."""
        root = self.tree.root_node

        # First pass: extract all comment annotations
        self._extract_all_annotations(root)

        # Second pass: process top-level constructs
        for child in root.children:
            self._visit_top_level(child)

    # ------------------------------------------------------------------
    # Annotation extraction
    # ------------------------------------------------------------------

    def _extract_all_annotations(self, root: ts.Node) -> None:
        """Extract unit annotations from all comments in the source."""
        self._collect_annotations_recursive(root)

    def _collect_annotations_recursive(self, node: ts.Node) -> None:
        """Recursively find comments containing unit annotations."""
        for child in node.children:
            if child.type == "comment":
                self._process_comment_annotation(child)
            if child.is_named:
                self._collect_annotations_recursive(child)

    def _process_comment_annotation(self, comment_node: ts.Node) -> None:
        """Extract a unit annotation from a comment node, if present."""
        text = self._node_text(comment_node)

        match = _FORTRAN_UNIT_RE.search(text)
        if not match:
            return

        unit_string = match.group(1).strip()
        comment_line = comment_node.start_point.row  # 0-based
        comment_col = comment_node.start_point.column

        # Determine which variable this annotation applies to
        var_name = self._resolve_annotation_target(comment_node)
        if not var_name:
            return

        loc = SourceLocation(self.file_path, comment_line + 1, comment_col)
        annotation = IRAnnotation(
            variable_name=var_name,
            scope="__pending__",
            unit_string=unit_string,
            location=loc,
        )
        self.module.annotations.append(annotation)

    def _resolve_annotation_target(self, comment_node: ts.Node) -> Optional[str]:
        """Determine which variable a comment annotation applies to.

        Rules:
        1. If the comment is on the same line as a declaration, use
           the last identifier in that declaration.
        2. If the comment is on the same line as an assignment, use
           the assignment target.
        3. If the comment is a standalone line, apply to the next
           declaration or assignment.
        """
        parent = comment_node.parent
        comment_line = comment_node.start_point.row

        if parent is None:
            return None

        # Look for preceding sibling on the same line
        prev = comment_node.prev_sibling
        if prev and prev.start_point.row == comment_line:
            name = self._extract_statement_var_name(prev)
            if name:
                return name

        # If standalone comment, look at next sibling
        next_sib = comment_node.next_sibling
        while next_sib:
            if next_sib.type == "comment":
                next_sib = next_sib.next_sibling
                continue
            name = self._extract_statement_var_name(next_sib)
            if name:
                return name
            break

        return None

    def _extract_statement_var_name(self, node: ts.Node) -> Optional[str]:
        """Extract the variable name from a declaration or assignment node."""
        if node.type == "variable_declaration":
            return self._get_declaration_var_name(node)
        if node.type == "assignment_statement":
            # First child is the target identifier
            for child in node.children:
                if child.type == "identifier":
                    return self._node_text(child).lower()
                break
        return None

    def _get_declaration_var_name(self, decl_node: ts.Node) -> Optional[str]:
        """Get the variable name(s) from a variable_declaration node.

        Returns the last identifier in the declaration (for single-var decls).
        """
        last_ident = None
        for child in decl_node.children:
            if child.type == "identifier":
                last_ident = self._node_text(child).lower()
        return last_ident

    # ------------------------------------------------------------------
    # Top-level node dispatch
    # ------------------------------------------------------------------

    def _visit_top_level(self, node: ts.Node) -> None:
        """Process a top-level node."""
        if node.type == "program":
            self._visit_program(node)
        elif node.type == "subroutine":
            self._visit_subroutine(node)
        elif node.type == "function":
            self._visit_function(node)
        elif node.type == "module":
            self._visit_module_block(node)
        elif node.type == "variable_declaration":
            # Top-level declarations (rare but possible in modules)
            pass
        elif node.type == "assignment_statement":
            stmt = self._visit_assignment(node, "global")
            if stmt:
                self.module.global_statements.append(stmt)

    # ------------------------------------------------------------------
    # Program blocks
    # ------------------------------------------------------------------

    def _visit_program(self, node: ts.Node) -> None:
        """Process a program block. Treat its body as global scope."""
        for child in node.children:
            if child.type == "variable_declaration":
                # Declarations introduce variables but no IR assignments
                # unless there's an initializer (handled below)
                pass
            elif child.type == "assignment_statement":
                stmt = self._visit_assignment(child, "global")
                if stmt:
                    self.module.global_statements.append(stmt)
            elif child.type == "subroutine":
                self._visit_subroutine(child)
            elif child.type == "function":
                self._visit_function(child)
            elif child.type == "if_statement":
                stmts = self._visit_if_statement(child, "global")
                self.module.global_statements.extend(stmts)
            elif child.type == "do_loop_statement":
                stmts = self._visit_do_loop(child, "global")
                self.module.global_statements.extend(stmts)

    def _visit_module_block(self, node: ts.Node) -> None:
        """Process a module block. Contains declarations and subprograms."""
        for child in node.children:
            if child.type == "subroutine":
                self._visit_subroutine(child)
            elif child.type == "function":
                self._visit_function(child)
            elif child.type == "contains_statement":
                pass  # The contained subprograms follow as siblings

    # ------------------------------------------------------------------
    # Subroutine / Function definitions
    # ------------------------------------------------------------------

    def _visit_subroutine(self, node: ts.Node) -> None:
        """Convert a Fortran subroutine to an IRFunction."""
        sub_name = None
        params: list[IRVariable] = []

        # Find subroutine_statement to get name and parameters
        for child in node.children:
            if child.type == "subroutine_statement":
                sub_name, params = self._extract_subprogram_header(child, "subroutine")
                break

        if sub_name is None:
            return

        sub_name = sub_name.lower()
        func_scope = f"local:{sub_name}"
        param_scope = f"param:{sub_name}"
        loc = self._loc(node)

        # Create parameter variables
        param_vars: list[IRVariable] = []
        for p in params:
            var = self._get_or_create_var(p.name, param_scope, p.location)
            param_vars.append(var)

        # Create synthetic return variable (subroutines don't truly return,
        # but we keep the convention for consistency)
        return_var = IRVariable(
            name=f"__return_{sub_name}__",
            scope=func_scope,
            location=loc,
        )

        # Process body
        body_stmts = self._visit_subprogram_body(node, func_scope)

        func = IRFunction(
            name=sub_name,
            parameters=param_vars,
            body=body_stmts,
            return_variable=return_var,
            location=loc,
        )
        self.module.functions.append(func)

    def _visit_function(self, node: ts.Node) -> None:
        """Convert a Fortran function to an IRFunction."""
        func_name = None
        result_name = None
        params: list[IRVariable] = []

        for child in node.children:
            if child.type == "function_statement":
                func_name, params = self._extract_subprogram_header(child, "function")
                result_name = self._extract_result_name(child)
                break

        if func_name is None:
            return

        func_name = func_name.lower()
        func_scope = f"local:{func_name}"
        param_scope = f"param:{func_name}"
        loc = self._loc(node)

        # Create parameter variables
        param_vars: list[IRVariable] = []
        for p in params:
            var = self._get_or_create_var(p.name, param_scope, p.location)
            param_vars.append(var)

        # Return variable
        return_var = IRVariable(
            name=f"__return_{func_name}__",
            scope=func_scope,
            location=loc,
        )

        # Process body
        body_stmts = self._visit_subprogram_body(node, func_scope)

        # If function has a result variable, create an equality constraint
        # by adding an assignment from result_var to __return_func__ at the end
        if result_name:
            result_name = result_name.lower()
            # The result variable assignments in the body will already target
            # the result variable name. We need to link it to the return var.
            result_var = self._get_or_create_var(result_name, func_scope, loc)
            # Add an assignment: __return_func__ = result_var
            body_stmts.append(IRAssignment(
                target=return_var,
                expression=IRVariableRef(variable=result_var, location=loc),
                location=loc,
            ))

        func = IRFunction(
            name=func_name,
            parameters=param_vars,
            body=body_stmts,
            return_variable=return_var,
            location=loc,
        )
        self.module.functions.append(func)

    def _extract_subprogram_header(
        self, stmt_node: ts.Node, kind: str
    ) -> tuple[Optional[str], list[IRVariable]]:
        """Extract name and parameters from a subroutine_statement or function_statement."""
        name = None
        params: list[IRVariable] = []

        for child in stmt_node.children:
            if child.type == "name":
                name = self._node_text(child).lower()
            elif child.type == "parameters":
                params = self._extract_parameters(child, name or "unknown")

        return name, params

    def _extract_result_name(self, func_stmt_node: ts.Node) -> Optional[str]:
        """Extract the result variable name from a function_statement."""
        for child in func_stmt_node.children:
            if child.type == "function_result":
                for sub in child.children:
                    if sub.type == "identifier":
                        return self._node_text(sub).lower()
        return None

    def _extract_parameters(self, param_node: ts.Node, func_name: str) -> list[IRVariable]:
        """Extract parameter names from a parameters node."""
        params: list[IRVariable] = []
        param_scope = f"param:{func_name.lower()}"

        for child in param_node.children:
            if child.type == "identifier":
                name = self._node_text(child).lower()
                var = IRVariable(
                    name=name,
                    scope=param_scope,
                    location=self._loc(child),
                )
                params.append(var)

        return params

    def _visit_subprogram_body(self, node: ts.Node, scope: str) -> list[IRStatement]:
        """Process the body statements of a subroutine or function."""
        stmts: list[IRStatement] = []
        for child in node.children:
            if child.type == "assignment_statement":
                stmt = self._visit_assignment(child, scope)
                if stmt:
                    stmts.append(stmt)
            elif child.type == "if_statement":
                stmts.extend(self._visit_if_statement(child, scope))
            elif child.type == "do_loop_statement":
                stmts.extend(self._visit_do_loop(child, scope))
            # variable_declaration, implicit_statement, etc. are skipped
        return stmts

    # ------------------------------------------------------------------
    # Control flow
    # ------------------------------------------------------------------

    def _visit_if_statement(self, node: ts.Node, scope: str) -> list[IRStatement]:
        """Process an if statement (both branches)."""
        stmts: list[IRStatement] = []
        for child in node.children:
            if child.type == "assignment_statement":
                stmt = self._visit_assignment(child, scope)
                if stmt:
                    stmts.append(stmt)
            elif child.type == "if_statement":
                stmts.extend(self._visit_if_statement(child, scope))
            elif child.type in ("body", "block"):
                stmts.extend(self._visit_block_children(child, scope))
        return stmts

    def _visit_do_loop(self, node: ts.Node, scope: str) -> list[IRStatement]:
        """Process a do loop body."""
        stmts: list[IRStatement] = []
        for child in node.children:
            if child.type == "assignment_statement":
                stmt = self._visit_assignment(child, scope)
                if stmt:
                    stmts.append(stmt)
            elif child.type == "if_statement":
                stmts.extend(self._visit_if_statement(child, scope))
            elif child.type == "do_loop_statement":
                stmts.extend(self._visit_do_loop(child, scope))
        return stmts

    def _visit_block_children(self, node: ts.Node, scope: str) -> list[IRStatement]:
        """Process children of a block node."""
        stmts: list[IRStatement] = []
        for child in node.children:
            if child.type == "assignment_statement":
                stmt = self._visit_assignment(child, scope)
                if stmt:
                    stmts.append(stmt)
            elif child.type == "if_statement":
                stmts.extend(self._visit_if_statement(child, scope))
            elif child.type == "do_loop_statement":
                stmts.extend(self._visit_do_loop(child, scope))
        return stmts

    # ------------------------------------------------------------------
    # Assignments
    # ------------------------------------------------------------------

    def _visit_assignment(self, node: ts.Node, scope: str) -> Optional[IRStatement]:
        """Convert an assignment_statement to an IRAssignment.

        assignment_statement children: identifier, =, expression
        """
        var_name = None
        rhs_expr = None
        seen_equals = False

        for child in node.children:
            if child.type == "=" and not child.is_named:
                seen_equals = True
                continue
            if not seen_equals:
                if child.type == "identifier":
                    var_name = self._node_text(child).lower()
            else:
                rhs_expr = child

        if var_name is None or rhs_expr is None:
            return None

        old_scope = self._current_scope
        self._current_scope = scope
        var = self._get_or_create_var(var_name, scope, self._loc(node))
        expr = self._visit_expression(rhs_expr, scope)
        self._current_scope = old_scope

        if expr is None:
            return None

        return IRAssignment(
            target=var,
            expression=expr,
            location=self._loc(node),
        )

    # ------------------------------------------------------------------
    # Expressions
    # ------------------------------------------------------------------

    def _visit_expression(self, node: ts.Node, scope: str) -> Optional[IRExpression]:
        """Convert a tree-sitter expression node to an IR expression."""
        loc = self._loc(node)

        if node.type == "number_literal":
            return self._visit_number_literal(node)

        if node.type == "identifier":
            name = self._node_text(node).lower()
            var = self._get_or_create_var(name, scope, loc)
            return IRVariableRef(variable=var, location=loc)

        if node.type == "math_expression":
            return self._visit_math_expression(node, scope)

        if node.type == "call_expression":
            return self._visit_call_expression(node, scope)

        if node.type == "unary_expression":
            return self._visit_unary_expression(node, scope)

        if node.type == "parenthesized_expression":
            for child in node.children:
                if child.type not in ("(", ")"):
                    return self._visit_expression(child, scope)

        if node.type == "relational_expression":
            return self._visit_relational_expression(node, scope)

        if node.type == "string_literal":
            return IRLiteral(value=0.0, location=loc)

        # Fallback: try to find a meaningful child
        for child in node.children:
            if child.type in ("number_literal", "identifier", "math_expression",
                              "call_expression", "unary_expression",
                              "parenthesized_expression"):
                return self._visit_expression(child, scope)

        return IRLiteral(value=0.0, location=loc)

    def _visit_number_literal(self, node: ts.Node) -> IRLiteral:
        """Convert a number literal to an IRLiteral."""
        text = self._node_text(node).strip()
        loc = self._loc(node)

        # Handle Fortran-style literals: 1.0d0, 1.0e5, 1.0_dp
        # Strip kind parameters (e.g., 1.0_dp -> 1.0)
        if "_" in text:
            text = text.split("_")[0]

        # Convert Fortran double-precision notation: 1.0d5 -> 1.0e5
        text = text.replace("d", "e").replace("D", "E")

        try:
            return IRLiteral(value=float(text), location=loc)
        except ValueError:
            return IRLiteral(value=0.0, location=loc)

    def _visit_math_expression(self, node: ts.Node, scope: str) -> Optional[IRExpression]:
        """Convert a math_expression (binary arithmetic) to IRBinaryOp."""
        loc = self._loc(node)

        # math_expression children: left_expr, operator, right_expr
        children = [c for c in node.children]
        if len(children) < 3:
            if children:
                return self._visit_expression(children[0], scope)
            return None

        left_node = children[0]
        op_text = self._node_text(children[1])
        right_node = children[2]

        # Check for comparison operators
        cmp_op = _CMP_MAP.get(op_text.lower())
        if cmp_op is not None:
            left = self._visit_expression(left_node, scope)
            right = self._visit_expression(right_node, scope)
            if left and right:
                return IRComparison(operator=cmp_op, left=left, right=right, location=loc)
            return None

        # Arithmetic operators
        bin_op = _BINOP_MAP.get(op_text)
        if bin_op is None:
            return self._visit_expression(left_node, scope)

        left = self._visit_expression(left_node, scope)
        right = self._visit_expression(right_node, scope)
        if left is None or right is None:
            return left or right

        return IRBinaryOp(operator=bin_op, left=left, right=right, location=loc)

    def _visit_unary_expression(self, node: ts.Node, scope: str) -> Optional[IRExpression]:
        """Convert a unary expression (e.g., -x, +x) to an IRUnaryOp."""
        loc = self._loc(node)

        if len(node.children) < 2:
            return None

        op_node = node.children[0]
        operand_node = node.children[1]
        op_text = self._node_text(op_node)

        operand = self._visit_expression(operand_node, scope)
        if operand is None:
            return None

        if op_text == "-":
            return IRUnaryOp(operator=UnaryOperator.NEG, operand=operand, location=loc)
        if op_text == "+":
            return IRUnaryOp(operator=UnaryOperator.POS, operand=operand, location=loc)

        return operand

    def _visit_call_expression(self, node: ts.Node, scope: str) -> Optional[IRExpression]:
        """Convert a call_expression to an IRCallExpr."""
        loc = self._loc(node)
        func_name = None
        args: list[IRExpression] = []

        for child in node.children:
            if child.type == "identifier":
                func_name = self._node_text(child).lower()
            elif child.type == "argument_list":
                args = self._visit_argument_list(child, scope)

        if func_name is None:
            return IRLiteral(value=0.0, location=loc)

        return IRCallExpr(
            function_name=func_name,
            arguments=args,
            location=loc,
        )

    def _visit_argument_list(self, node: ts.Node, scope: str) -> list[IRExpression]:
        """Extract arguments from an argument_list node."""
        args: list[IRExpression] = []
        for child in node.children:
            if child.type in ("(", ")", ","):
                continue
            expr = self._visit_expression(child, scope)
            if expr is not None:
                args.append(expr)
        return args

    def _visit_relational_expression(self, node: ts.Node, scope: str) -> Optional[IRExpression]:
        """Convert a relational_expression to an IRComparison."""
        loc = self._loc(node)
        children = [c for c in node.children]
        if len(children) < 3:
            return None

        left = self._visit_expression(children[0], scope)
        op_text = self._node_text(children[1]).lower()
        right = self._visit_expression(children[2], scope)

        if left is None or right is None:
            return None

        cmp_op = _CMP_MAP.get(op_text)
        if cmp_op:
            return IRComparison(operator=cmp_op, left=left, right=right, location=loc)

        return left

    # ------------------------------------------------------------------
    # Variable management
    # ------------------------------------------------------------------

    def _get_or_create_var(self, name: str, scope: str, location: SourceLocation) -> IRVariable:
        """Get an existing variable or create a new one in the given scope.

        Fortran is case-insensitive, so names are always lowered.
        """
        name = name.lower()
        scope_vars = self._variables.setdefault(scope, {})

        if name in scope_vars:
            return scope_vars[name]

        # If in a local function scope, check parameters first
        if scope.startswith("local:"):
            func_name = scope[6:]
            param_scope = f"param:{func_name}"
            param_vars = self._variables.get(param_scope, {})
            if name in param_vars:
                scope_vars[name] = param_vars[name]
                return param_vars[name]

        var = IRVariable(
            name=name,
            scope=scope,
            location=location,
            annotation=None,
        )
        scope_vars[name] = var
        return var

    # ------------------------------------------------------------------
    # Helpers: tree-sitter utilities
    # ------------------------------------------------------------------

    def _node_text(self, node: ts.Node) -> str:
        """Get the source text of a tree-sitter node."""
        return self.source_bytes[node.start_byte:node.end_byte].decode("utf-8")

    def _loc(self, node: ts.Node) -> SourceLocation:
        """Convert a tree-sitter node position to a SourceLocation."""
        row = node.start_point.row  # 0-based
        col = node.start_point.column
        return SourceLocation(self.file_path, row + 1, col)

    def _next_temp_name(self) -> str:
        """Generate a unique temporary variable name."""
        self._temp_counter += 1
        return f"__temp_{self._temp_counter}__"
