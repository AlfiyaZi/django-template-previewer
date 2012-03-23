from django.template.base import Node, TextNode, VariableNode
from django.template.defaulttags import (
    CycleNode, FilterNode, FirstOfNode, IfNode, IfChangedNode,
    IfEqualNode, LoadNode, NowNode, SpacelessNode, URLNode, WidthRatioNode)

from django.template.loader import get_template
from django.template.loader_tags import BlockNode, ExtendsNode


def _get_vars(filter_expression):
    """
    Return the list of vars used in a django filter expressions. That includes
    the main var and any filter arguments
    """
    if not hasattr(filter_expression.var, 'var'):
        # Probably a string literal or something like that
        result = []
    else:
        result = [filter_expression.var.var]
    for _, arglist in filter_expression.filters:
        result.extend(arg.var for lookup, arg in arglist if lookup)
    return result


# The following are nodes that require no special treatment
_IGNORED_NODES = (TextNode, BlockNode, NowNode, LoadNode, SpacelessNode)


def _get_node_context(node):
    """
    Return the list of vars used in a node
    """
    result = []
    # Ignored nodes
    if isinstance(node, _IGNORED_NODES):
        pass
    # Simple variables
    elif isinstance(node, VariableNode):
        result = _get_vars(node.filter_expression)
    # Tags with arguments or some other magic
    elif isinstance(node, CycleNode):
        for expr in node.cyclevars:
            result += _get_vars(expr)
    elif isinstance(node, FilterNode):
        # The filter expr gets a "var|" prepended; so we remove it
        # with [1:]
        result = _get_vars(node.filter_expr)[1:]
    elif isinstance(node, FirstOfNode):
        for expr in node.vars:
            result += _get_vars(expr)
    elif isinstance(node, IfNode):
        result = _get_expression_vars(node.var)
    elif isinstance(node, IfChangedNode):
        for var in node._varlist:
            result += _get_vars(var)
    elif isinstance(node, IfEqualNode):
        result = _get_vars(node.var1) + _get_vars(node.var2)
    elif isinstance(node, URLNode):
        if not node.legacy_view_name:  # Django 1.3 new url tag
            result += _get_vars(node.view_name)
        for arg in node.args:
            result += _get_vars(arg)
        for key, arg in node.kwargs.items():
            result += _get_vars(arg)
    elif isinstance(node, WidthRatioNode):
        result = _get_vars(node.val_expr) + \
                 _get_vars(node.max_expr) + \
                 _get_vars(node.max_width)
    # Loading of another templates
    elif isinstance(node, ExtendsNode):
        if not node.parent_name_expr:
            # The included template is fixed. If it were dynamic there'd be
            # nothing more we can do
            parent = get_template(node.parent_name)
            result += get_context(parent)
    # Templates that introduce aliases to existing vars
    else:
        assert False, "Unrecognized node %s" % type(node)
        # TODO: for (hard, the iterable, but also the renamings. Also, the forloop stuff?)
        # TODO: include (the argument and the loaded template with renamings)
        # TODO: regroup (the arg, and renamings)
        # TODO: with: renamings

    # Go through children nodes. [1:] is to skip self
    for child in node.get_nodes_by_type(Node)[1:]:
        result += _get_node_context(child)

    return result


def _get_expression_vars(expr):
    """get variables used on an "if" expression"""
    result = []
    if hasattr(expr, 'value') and expr.value:
        result += _get_vars(expr.value)
    if hasattr(expr, 'first') and expr.first:
        result += _get_expression_vars(expr.first)
    if hasattr(expr, 'second') and expr.second:
        result += _get_expression_vars(expr.second)
    return result


def get_context(template):
    """
    Returns a list of context variables used in the template. Each variable is
    represented as a dotted string from the context root.

    The argument is a template object, not just a filename.

    For example, passing the template {{ var }} {{ var.attribute }}
    Results in: ["var", "var.attribute"]

    And {% with local=var.attribute %}local.inner{% endwith %}
    Results in: ["var", "var.attribute", "var.attribute.inner"]

    Custom template tags may not be interpreted correctly, but any argument
    to a template tag that isn't quoted is used as a variable.
    """

    result = []
    for node in template.nodelist:
        result += _get_node_context(node)

    return result


