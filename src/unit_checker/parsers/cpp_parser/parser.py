"""C++ source code parser using tree-sitter.

Uses the tree-sitter-cpp grammar to convert C++ source into the
language-independent IR consumed by the constraint builder.

Handles:
    - Variable declarations with initializers (int, float, double, auto, const)
    - Arithmetic expressions (+, -, *, /, with pow() for exponentiation)
    - Function definitions with parameters
    - Function calls (including qualified calls like std::pow)
    - Return statements
    - Assignment expressions (=, +=, -=, *=, /=)
    - Unit annotations from comments (// unit: m/s  or  /* unit: kg */)
    - Pointer and reference declarators (treated same as value for unit purposes)
    - Unary operators (-, +)
    - Comparison expressions (==, !=, <, <=, >, >=)

Does NOT handle (MVP):
    - Class definitions / methods
    - Templates
    - Namespaces (other than recognising std:: calls)
    - Lambda expressions
    - Structured bindings
    - Range-for / iterators
    - Preprocessor macros (other than skipping #include)
    - Exception handling
"""

from __future__ import annotations

import re
from typing import Optional

import tree_sitter_cpp as tscpp
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
    IRReturn,
    IRAugmentedAssignment,
    IRAnnotation,
    IRFunction,
    IRModule,
)

# Regex patterns for unit annotations in C++ comments
_SINGLE_LINE_UNIT_RE = re.compile(r"//\s*unit:\s*(\S+(?:[*/^]\S+)*)")
_BLOCK_UNIT_RE = re.compile(r"/\*\s*unit:\s*(.+?)\s*\*/")

# C++ binary operators -> IR operators
_BINOP_MAP: dict[str, BinaryOperator] = {
    "+": BinaryOperator.ADD,
    "-": BinaryOperator.SUB,
    "*": BinaryOperator.MUL,
    "/": BinaryOperator.DIV,
    "%": BinaryOperator.MOD,
}

# C++ augmented assignment operators -> IR operators
_AUG_ASSIGN_MAP: dict[str, BinaryOperator] = {
    "+=": BinaryOperator.ADD,
    "-=": BinaryOperator.SUB,
    "*=": BinaryOperator.MUL,
    "/=": BinaryOperator.DIV,
    "%=": BinaryOperator.MOD,
}

# C++ comparison operators -> IR operators
_CMP_MAP: dict[str, ComparisonOperator] = {
    "==": ComparisonOperator.EQ,
    "!=": ComparisonOperator.NE,
    "<": ComparisonOperator.LT,
    "<=": ComparisonOperator.LE,
    ">": ComparisonOperator.GT,
    ">=": ComparisonOperator.GE,
}

# C++ numeric types we recognise (for filtering declarations)
_NUMERIC_TYPES = frozenset({
    "int", "float", "double", "long", "short",
    "unsigned", "signed", "char",
    "int8_t", "int16_t", "int32_t", "int64_t",
    "uint8_t", "uint16_t", "uint32_t", "uint64_t",
    "size_t", "ssize_t", "ptrdiff_t",
})

# Lazy-initialised parser and language (module-level singletons)
_ts_language: Optional[ts.Language] = None
_ts_parser: Optional[ts.Parser] = None


def _get_parser() -> ts.Parser:
    """Return (and lazily initialise) the tree-sitter C++ parser."""
    global _ts_language, _ts_parser
    if _ts_parser is None:
        _ts_language = ts.Language(tscpp.language())
        _ts_parser = ts.Parser(_ts_language)
    return _ts_parser


def parse_cpp(source: str, file_path: str = "<string>") -> IRModule:
    """Parse C++ source code into an IRModule.

    Args:
        source: C++ source code string.
        file_path: Path to the source file (for error reporting).

    Returns:
        IRModule with all functions, global statements, and annotations.
    """
    parser = _get_parser()
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)

    builder = _CppIRBuilder(file_path, source, source_bytes, tree)
    builder.build()
    return builder.module


class _CppIRBuilder:
    """Walks the tree-sitter C++ AST and builds IR nodes."""

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

        # Second pass: process top-level declarations and definitions
        for child in root.children:
            self._visit_top_level(child)

    # ------------------------------------------------------------------
    # Annotation extraction
    # ------------------------------------------------------------------

    def _extract_all_annotations(self, root: ts.Node) -> None:
        """Extract unit annotations from all comments in the source.

        Supported formats:
            // unit: m/s           (single-line, applies to preceding or next declaration)
            /* unit: kg */         (block, applies to preceding or next declaration)
            void f(double v /* unit: m/s */)  (inline parameter annotation)
        """
        # Walk all children at every level to find comments
        self._collect_annotations_recursive(root)

    def _collect_annotations_recursive(self, node: ts.Node) -> None:
        """Recursively find comments containing unit annotations."""
        for child in node.children:
            if child.type == "comment":
                self._process_comment_annotation(child)
            # Recurse into named children to catch parameter-level comments
            if child.is_named:
                self._collect_annotations_recursive(child)

    def _process_comment_annotation(self, comment_node: ts.Node) -> None:
        """Extract a unit annotation from a comment node, if present."""
        text = self._node_text(comment_node)

        # Try single-line comment
        match = _SINGLE_LINE_UNIT_RE.search(text)
        if not match:
            # Try block comment
            match = _BLOCK_UNIT_RE.search(text)
        if not match:
            return

        unit_string = match.group(1).strip()
        comment_line = comment_node.start_point.row  # 0-based
        comment_col = comment_node.start_point.column

        # Determine which variable this annotation applies to.
        # Strategy: look at siblings.
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
        1. If the comment is on the same line as a declaration, use that declaration's variable.
        2. If the comment is between parameters (inside a parameter_list), use the preceding parameter.
        3. If the comment is a standalone line, apply to the next declaration.
        """
        parent = comment_node.parent

        # Case: comment inside a parameter_list (inline parameter annotation)
        if parent and parent.type == "parameter_list":
            return self._find_preceding_param_name(parent, comment_node)

        # Case: comment inside a compound_statement (function body)
        if parent and parent.type == "compound_statement":
            return self._find_var_on_same_or_adjacent_line(parent, comment_node)

        # Case: comment at top level (translation_unit)
        if parent and parent.type == "translation_unit":
            return self._find_var_on_same_or_adjacent_line(parent, comment_node)

        return None

    def _find_preceding_param_name(self, param_list: ts.Node, comment_node: ts.Node) -> Optional[str]:
        """Find the parameter name preceding this comment within a parameter_list."""
        prev_param = None
        for child in param_list.children:
            if child.id == comment_node.id:
                break
            if child.type == "parameter_declaration":
                prev_param = child
        if prev_param is not None:
            return self._extract_param_name(prev_param)
        return None

    def _find_var_on_same_or_adjacent_line(self, parent: ts.Node, comment_node: ts.Node) -> Optional[str]:
        """Find variable on same line (preceding declaration) or next line (following declaration)."""
        comment_line = comment_node.start_point.row

        # Look for a declaration on the same line (preceding sibling)
        prev_sibling = comment_node.prev_sibling
        if prev_sibling and prev_sibling.start_point.row == comment_line:
            name = self._extract_declaration_var_name(prev_sibling)
            if name:
                return name

        # If comment is on its own line, look at the next declaration
        next_sibling = comment_node.next_sibling
        while next_sibling:
            if next_sibling.type == "comment":
                next_sibling = next_sibling.next_sibling
                continue
            name = self._extract_declaration_var_name(next_sibling)
            if name:
                return name
            break

        return None

    def _extract_declaration_var_name(self, node: ts.Node) -> Optional[str]:
        """Extract the variable name from a declaration or expression_statement node."""
        if node.type == "declaration":
            return self._get_declarator_name(node)
        if node.type == "expression_statement":
            # Could be an assignment: a = expr;
            for child in node.children:
                if child.type == "assignment_expression":
                    lhs = child.children[0] if child.children else None
                    if lhs and lhs.type == "identifier":
                        return self._node_text(lhs)
        return None

    def _extract_param_name(self, param_node: ts.Node) -> Optional[str]:
        """Extract parameter name from a parameter_declaration node."""
        for child in param_node.children:
            if child.type == "identifier":
                return self._node_text(child)
            # Handle reference/pointer parameter declarators
            if child.type in ("reference_declarator", "pointer_declarator"):
                for sub in child.children:
                    if sub.type == "identifier":
                        return self._node_text(sub)
        return None

    # ------------------------------------------------------------------
    # Top-level node dispatch
    # ------------------------------------------------------------------

    def _visit_top_level(self, node: ts.Node) -> None:
        """Process a top-level node (declaration, function definition, etc.)."""
        if node.type == "function_definition":
            self._visit_function_definition(node)
        elif node.type == "declaration":
            stmts = self._visit_declaration(node, "global")
            self.module.global_statements.extend(stmts)
        elif node.type == "expression_statement":
            stmts = self._visit_expression_statement(node, "global")
            self.module.global_statements.extend(stmts)
        # Skip: comment, preproc_include, preproc_def, namespace_definition, etc.

    # ------------------------------------------------------------------
    # Function definitions
    # ------------------------------------------------------------------

    def _visit_function_definition(self, node: ts.Node) -> None:
        """Convert a C++ function definition to an IRFunction."""
        # Find function name and parameters from the function_declarator
        func_name = None
        params: list[IRVariable] = []
        func_decl = None

        for child in node.children:
            if child.type == "function_declarator":
                func_decl = child
                break

        if func_decl is None:
            return

        # Extract function name
        for child in func_decl.children:
            if child.type == "identifier":
                func_name = self._node_text(child)
                break

        if func_name is None:
            return

        func_scope = f"local:{func_name}"
        loc = self._loc(node)

        # Extract parameters from parameter_list
        for child in func_decl.children:
            if child.type == "parameter_list":
                params = self._extract_parameters(child, func_name)
                break

        # Create synthetic return variable
        return_var = IRVariable(
            name=f"__return_{func_name}__",
            scope=func_scope,
            location=loc,
        )

        # Process function body (compound_statement)
        body_stmts: list[IRStatement] = []
        for child in node.children:
            if child.type == "compound_statement":
                body_stmts = self._visit_compound_statement(child, func_scope)
                break

        func = IRFunction(
            name=func_name,
            parameters=params,
            body=body_stmts,
            return_variable=return_var,
            location=loc,
        )
        self.module.functions.append(func)

    def _extract_parameters(self, param_list: ts.Node, func_name: str) -> list[IRVariable]:
        """Extract parameter variables from a parameter_list node."""
        params: list[IRVariable] = []
        param_scope = f"param:{func_name}"

        for child in param_list.children:
            if child.type == "parameter_declaration":
                name = self._extract_param_name(child)
                if name:
                    var = self._get_or_create_var(name, param_scope, self._loc(child))
                    params.append(var)
        return params

    # ------------------------------------------------------------------
    # Compound statement (function body, block)
    # ------------------------------------------------------------------

    def _visit_compound_statement(self, node: ts.Node, scope: str) -> list[IRStatement]:
        """Process all statements inside a compound_statement (block)."""
        stmts: list[IRStatement] = []
        for child in node.children:
            if child.type == "declaration":
                stmts.extend(self._visit_declaration(child, scope))
            elif child.type == "expression_statement":
                stmts.extend(self._visit_expression_statement(child, scope))
            elif child.type == "return_statement":
                stmt = self._visit_return_statement(child, scope)
                if stmt:
                    stmts.append(stmt)
            elif child.type == "compound_statement":
                # Nested block
                stmts.extend(self._visit_compound_statement(child, scope))
            elif child.type == "if_statement":
                stmts.extend(self._visit_if_statement(child, scope))
            elif child.type == "for_statement":
                stmts.extend(self._visit_for_statement(child, scope))
            elif child.type == "while_statement":
                stmts.extend(self._visit_while_statement(child, scope))
        return stmts

    def _visit_if_statement(self, node: ts.Node, scope: str) -> list[IRStatement]:
        """Process an if statement (both branches)."""
        stmts: list[IRStatement] = []
        for child in node.children:
            if child.type == "compound_statement":
                stmts.extend(self._visit_compound_statement(child, scope))
            elif child.type == "else_clause":
                for sub in child.children:
                    if sub.type == "compound_statement":
                        stmts.extend(self._visit_compound_statement(sub, scope))
                    elif sub.type == "if_statement":
                        stmts.extend(self._visit_if_statement(sub, scope))
        return stmts

    def _visit_for_statement(self, node: ts.Node, scope: str) -> list[IRStatement]:
        """Process a for loop body."""
        stmts: list[IRStatement] = []
        for child in node.children:
            if child.type == "compound_statement":
                stmts.extend(self._visit_compound_statement(child, scope))
        return stmts

    def _visit_while_statement(self, node: ts.Node, scope: str) -> list[IRStatement]:
        """Process a while loop body."""
        stmts: list[IRStatement] = []
        for child in node.children:
            if child.type == "compound_statement":
                stmts.extend(self._visit_compound_statement(child, scope))
        return stmts

    # ------------------------------------------------------------------
    # Declarations
    # ------------------------------------------------------------------

    def _visit_declaration(self, node: ts.Node, scope: str) -> list[IRStatement]:
        """Convert a C++ declaration to IR statements.

        Handles:
            double x = expr;       -> IRAssignment
            int a = 5, b = 10;     -> multiple IRAssignments
            const double& r = y;   -> IRAssignment (ignoring const/ref)
        """
        stmts: list[IRStatement] = []

        for child in node.children:
            if child.type == "init_declarator":
                stmt = self._visit_init_declarator(child, scope, node)
                if stmt:
                    stmts.append(stmt)
        return stmts

    def _visit_init_declarator(self, node: ts.Node, scope: str, decl_node: ts.Node) -> Optional[IRStatement]:
        """Convert an init_declarator (name = expr) to an IRAssignment."""
        var_name = None
        init_expr = None
        seen_equals = False

        for child in node.children:
            if child.type == "=" and not child.is_named:
                seen_equals = True
                continue
            if not seen_equals:
                # Before the '=': this is the declarator (name part)
                if child.type == "identifier":
                    var_name = self._node_text(child)
                elif child.type in ("reference_declarator", "pointer_declarator"):
                    # double& x or double* x -- extract the identifier
                    for sub in child.children:
                        if sub.type == "identifier":
                            var_name = self._node_text(sub)
            else:
                # After the '=': this is the initializer expression
                if child.type not in (",", ";"):
                    init_expr = child

        if var_name is None:
            return None
        if init_expr is None:
            # Declaration without initializer (e.g., `double x;`)
            return None

        old_scope = self._current_scope
        self._current_scope = scope
        var = self._get_or_create_var(var_name, scope, self._loc(decl_node))
        expr = self._visit_expression(init_expr, scope)
        self._current_scope = old_scope

        if expr is None:
            return None

        return IRAssignment(
            target=var,
            expression=expr,
            location=self._loc(decl_node),
        )

    # ------------------------------------------------------------------
    # Expression statements (assignments, augmented assignments)
    # ------------------------------------------------------------------

    def _visit_expression_statement(self, node: ts.Node, scope: str) -> list[IRStatement]:
        """Process an expression_statement (e.g., `a = b + c;` or `a += 5;`)."""
        stmts: list[IRStatement] = []
        for child in node.children:
            if child.type == "assignment_expression":
                stmt = self._visit_assignment_expression(child, scope)
                if stmt:
                    stmts.append(stmt)
        return stmts

    def _visit_assignment_expression(self, node: ts.Node, scope: str) -> Optional[IRStatement]:
        """Convert an assignment_expression to IR.

        Handles both simple (=) and augmented (+=, -=, etc.) assignments.
        """
        if len(node.children) < 3:
            return None

        lhs_node = node.children[0]
        op_node = node.children[1]
        rhs_node = node.children[2]

        op_text = self._node_text(op_node)

        if lhs_node.type != "identifier":
            return None

        var_name = self._node_text(lhs_node)
        old_scope = self._current_scope
        self._current_scope = scope
        var = self._get_or_create_var(var_name, scope, self._loc(node))
        rhs_expr = self._visit_expression(rhs_node, scope)
        self._current_scope = old_scope

        if rhs_expr is None:
            return None

        if op_text == "=":
            return IRAssignment(
                target=var,
                expression=rhs_expr,
                location=self._loc(node),
            )

        # Augmented assignment
        ir_op = _AUG_ASSIGN_MAP.get(op_text)
        if ir_op is not None:
            return IRAugmentedAssignment(
                target=var,
                operator=ir_op,
                expression=rhs_expr,
                location=self._loc(node),
            )

        return None

    # ------------------------------------------------------------------
    # Return statements
    # ------------------------------------------------------------------

    def _visit_return_statement(self, node: ts.Node, scope: str) -> Optional[IRStatement]:
        """Convert a return statement to an IRReturn."""
        # return_statement children: "return", <expression>, ";"
        for child in node.children:
            if child.type not in ("return", ";"):
                old_scope = self._current_scope
                self._current_scope = scope
                expr = self._visit_expression(child, scope)
                self._current_scope = old_scope
                if expr is not None:
                    return IRReturn(expression=expr, location=self._loc(node))
        return None

    # ------------------------------------------------------------------
    # Expressions
    # ------------------------------------------------------------------

    def _visit_expression(self, node: ts.Node, scope: str) -> Optional[IRExpression]:
        """Convert a tree-sitter expression node to an IR expression."""
        loc = self._loc(node)

        if node.type == "number_literal":
            return self._visit_number_literal(node)

        if node.type == "identifier":
            var = self._get_or_create_var(self._node_text(node), scope, loc)
            return IRVariableRef(variable=var, location=loc)

        if node.type == "binary_expression":
            return self._visit_binary_expression(node, scope)

        if node.type == "unary_expression":
            return self._visit_unary_expression(node, scope)

        if node.type == "call_expression":
            return self._visit_call_expression(node, scope)

        if node.type == "parenthesized_expression":
            # (expr) -- unwrap
            for child in node.children:
                if child.type not in ("(", ")"):
                    return self._visit_expression(child, scope)

        if node.type == "conditional_expression":
            # ternary: cond ? a : b -- use the true branch for units
            children = [c for c in node.children if c.type not in ("?", ":")]
            if len(children) >= 2:
                return self._visit_expression(children[1], scope)

        if node.type == "pointer_expression":
            # &x or *ptr -- for unit purposes, same unit as operand
            for child in node.children:
                if child.type == "identifier":
                    var = self._get_or_create_var(self._node_text(child), scope, loc)
                    return IRVariableRef(variable=var, location=loc)

        if node.type == "assignment_expression":
            # Embedded assignment within an expression -- visit RHS
            if len(node.children) >= 3:
                return self._visit_expression(node.children[2], scope)

        # Fallback: unknown expression type -> literal 0
        return IRLiteral(value=0.0, location=loc)

    def _visit_number_literal(self, node: ts.Node) -> IRLiteral:
        """Convert a number literal to an IRLiteral."""
        text = self._node_text(node)
        loc = self._loc(node)
        try:
            # Handle hex and binary literals BEFORE stripping suffixes,
            # because hex digits overlap with C++ type suffixes (e.g., 0xFF).
            if text.startswith(("0x", "0X")):
                # Strip only integer suffixes from the end (u, U, l, L)
                cleaned = text.rstrip("uUlL")
                return IRLiteral(value=float(int(cleaned, 16)), location=loc)
            if text.startswith(("0b", "0B")):
                cleaned = text.rstrip("uUlL")
                return IRLiteral(value=float(int(cleaned, 2)), location=loc)
            # For decimal/float literals, strip type suffixes: f, F, l, L, u, U
            cleaned = text.rstrip("fFlLuU")
            return IRLiteral(value=float(cleaned), location=loc)
        except ValueError:
            return IRLiteral(value=0.0, location=loc)

    def _visit_binary_expression(self, node: ts.Node, scope: str) -> Optional[IRExpression]:
        """Convert a binary expression to an IRBinaryOp or IRComparison."""
        loc = self._loc(node)

        if len(node.children) < 3:
            return None

        left_node = node.children[0]
        op_node = node.children[1]
        right_node = node.children[2]
        op_text = self._node_text(op_node)

        # Check for comparison operator
        cmp_op = _CMP_MAP.get(op_text)
        if cmp_op is not None:
            left = self._visit_expression(left_node, scope)
            right = self._visit_expression(right_node, scope)
            if left and right:
                return IRComparison(operator=cmp_op, left=left, right=right, location=loc)
            return None

        # Check for arithmetic operator
        bin_op = _BINOP_MAP.get(op_text)
        if bin_op is None:
            # Unknown operator (&&, ||, <<, >>, etc.) -- fallback
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

        # Other unary ops (!, ~, ++, --): return operand
        return operand

    def _visit_call_expression(self, node: ts.Node, scope: str) -> Optional[IRExpression]:
        """Convert a call expression to an IRCallExpr.

        Handles:
            func(args)               -> IRCallExpr("func", args)
            std::func(args)          -> IRCallExpr("std::func", args)
            pow(base, exp)           -> IRBinaryOp(POW, base, exp)  [special case]
        """
        loc = self._loc(node)
        func_name = None
        args: list[IRExpression] = []

        for child in node.children:
            if child.type == "identifier":
                func_name = self._node_text(child)
            elif child.type == "qualified_identifier":
                func_name = self._node_text(child)
            elif child.type == "argument_list":
                args = self._visit_argument_list(child, scope)

        if func_name is None:
            return IRLiteral(value=0.0, location=loc)

        # Special case: pow(base, exponent) -> IRBinaryOp(POW, base, exp)
        if func_name in ("pow", "std::pow", "powf", "powl") and len(args) == 2:
            return IRBinaryOp(
                operator=BinaryOperator.POW,
                left=args[0],
                right=args[1],
                location=loc,
            )

        # Special case: sqrt(x) -> IRCallExpr (handled by constraint builder)
        # No special IR transformation needed; the constraint builder already
        # recognises sqrt/std::sqrt.

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

    # ------------------------------------------------------------------
    # Variable management
    # ------------------------------------------------------------------

    def _get_or_create_var(self, name: str, scope: str, location: SourceLocation) -> IRVariable:
        """Get an existing variable or create a new one in the given scope.

        Mirrors the Python parser's variable deduplication logic.
        """
        scope_vars = self._variables.setdefault(scope, {})

        if name in scope_vars:
            return scope_vars[name]

        # If we are in a local function scope, check parameters first
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
    # Helpers: declaration name extraction
    # ------------------------------------------------------------------

    def _get_declarator_name(self, decl_node: ts.Node) -> Optional[str]:
        """Get the variable name from a declaration node."""
        for child in decl_node.children:
            if child.type == "init_declarator":
                for sub in child.children:
                    if sub.type == "identifier":
                        return self._node_text(sub)
                    if sub.type in ("reference_declarator", "pointer_declarator"):
                        for subsub in sub.children:
                            if subsub.type == "identifier":
                                return self._node_text(subsub)
        return None

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
