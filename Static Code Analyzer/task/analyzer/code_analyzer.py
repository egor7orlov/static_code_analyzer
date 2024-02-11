import os
import re
import sys
import ast


def is_line_too_long(line_of_code):
    return len(line_of_code.rstrip()) > 79


def is_indentation_not_multiple_of_four(line_of_code):
    leading_spaces = len(line_of_code) - len(line_of_code.lstrip(' '))
    return leading_spaces % 4 != 0 and leading_spaces != 0


def has_unnecessary_semicolon(line_of_code):
    clean_line = line_of_code.split('#', 1)[0].rstrip()
    return clean_line.endswith(';') and clean_line != ';'


def has_less_than_two_spaces_before_inline_comment(line_of_code):
    if '#' in line_of_code:
        parts = line_of_code.split('#', 1)
        if len(parts[0]) and not parts[0].endswith('  ') and not parts[
            0].endswith('\t'):
            return True
    return False


def has_todo_comment(line_of_code):
    comment_parts = line_of_code.split('#')
    if len(comment_parts) > 1:
        comment = comment_parts[1]
        return 'todo' in comment.lower()
    return False


def check_too_many_spaces_after_construction_name(line_of_code):
    match_class = re.match(r"\bclass\s{2,}", line_of_code)
    match_def = re.match(r"\bdef\s{2,}", line_of_code.lstrip())
    if match_class:
        return True, 'class'
    if match_def:
        return True, 'def'
    return False, None


def is_camel_case(name):
    return re.match(r'^[A-Z]([a-z0-9]+[A-Z]?)*$', name) is not None


def is_snake_case(name):
    return re.match(r'^_?[a-z0-9]+(_[a-z0-9]+)*_?$', name) is not None


def has_more_than_two_blank_lines(lines):
    issue_lines = []
    blank_line_count = 0
    for i, line in enumerate(lines):
        if line.strip() == '':
            blank_line_count += 1
        else:
            if blank_line_count > 2:
                issue_lines.append(i - blank_line_count + blank_line_count + 1)
            blank_line_count = 0
    return issue_lines


def analyze_code_with_ast(code, filepath):
    tree = ast.parse(code)
    issues = check_function_defs(tree, filepath)
    return issues


def check_function_defs(tree, filepath):
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Check if the function name is a special method name (dunder method)
            if not (node.name.startswith('__') and node.name.endswith('__')):
                if not is_snake_case(node.name):
                    issues.append(
                        (node.lineno,
                         f"S009 Function name '{node.name}' should use snake_case",
                         filepath)
                    )
            issues.extend(check_function_args(node, filepath))
            issues.extend(check_function_body_for_variables(node, filepath))
            issues.extend(check_mutable_default_arguments(node, filepath))
    return issues


def check_function_args(node, filepath):
    issues = []
    for arg in node.args.args:
        if not is_snake_case(arg.arg):
            issues.append(
                (arg.lineno,
                 f"S010 Argument name '{arg.arg}' should be snake_case",
                 filepath)
            )
    return issues


def check_function_body_for_variables(node, filepath):
    issues = []
    for body_node in ast.walk(node):
        if isinstance(body_node, ast.Assign):
            for target in body_node.targets:
                if isinstance(target, ast.Name) and not is_snake_case(
                        target.id
                ):
                    issues.append(
                        (body_node.lineno,
                         f"S011 Variable '{target.id}' in function should be snake_case",
                         filepath)
                    )
    return issues


def check_mutable_default_arguments(node, filepath):
    issues = []
    for default in node.args.defaults:
        if isinstance(default, (ast.List, ast.Dict, ast.Set)):
            issues.append(
                (
                    node.lineno, "S012 Default argument value is mutable",
                    filepath)
            )
    return issues


def analyze_file(file_path):
    with open(file_path, 'r') as file:
        code = file.read()
    lines = code.splitlines()
    issues = []

    for line_number, line_of_code in enumerate(lines, start=1):
        if is_line_too_long(line_of_code):
            issues.append((line_number, 'S001 Too long', file_path))
        if is_indentation_not_multiple_of_four(line_of_code):
            issues.append(
                (line_number, 'S002 Indentation is not a multiple of four',
                 file_path)
            )
        if has_unnecessary_semicolon(line_of_code):
            issues.append(
                (line_number, 'S003 Unnecessary semicolon', file_path)
            )
        if has_less_than_two_spaces_before_inline_comment(line_of_code):
            issues.append(
                (line_number,
                 'S004 At least two spaces required before inline comments',
                 file_path)
            )
        if has_todo_comment(line_of_code):
            issues.append((line_number, 'S005 TODO found', file_path))
        too_many_spaces, construction_name = check_too_many_spaces_after_construction_name(
            line_of_code
        )
        if too_many_spaces:
            issues.append(
                (line_number,
                 f"S007 Too many spaces after '{construction_name}'", file_path)
            )
        class_match = re.match(r"class\s+(\w+)", line_of_code)
        if class_match:
            class_name = class_match.group(1)
            if not is_camel_case(class_name):
                issues.append(
                    (line_number,
                     f"S008 Class name '{class_name}' should use CamelCase",
                     file_path)
                )

    excessive_blank_lines = has_more_than_two_blank_lines(lines)
    for line_number in excessive_blank_lines:
        issues.append(
            (line_number, 'S006 More than two blank lines used', file_path)
        )

    issues.extend(analyze_code_with_ast(code, file_path))
    return issues


def analyze_directory(directory_path):
    all_issues = []
    for root, dirs, files in os.walk(directory_path):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                file_issues = analyze_file(file_path)
                all_issues.extend(file_issues)
    return all_issues


def print_file_issues(file_path, issues):
    # Convert file_path to a relative path
    relative_path = os.path.relpath(file_path, start=os.getcwd())
    for line_number, message, _ in sorted(issues, key=lambda x: x[0]):
        print(f"{relative_path}: Line {line_number}: {message}")


def print_issues(issues):
    # Sort issues by file path, then by line number, and then by issue code
    sorted_issues = sorted(issues, key=lambda x: (x[2], x[0], x[1]))
    for line_number, message, file_path in sorted_issues:
        relative_path = os.path.relpath(file_path, start=os.getcwd())
        print(f"{relative_path}: Line {line_number}: {message}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(
            "Usage: python code_analyzer.py <path-to-python-file-or-directory>"
        )
        sys.exit(1)

    path = sys.argv[1]
    issues = []

    if os.path.isdir(path):
        issues = analyze_directory(path)
    elif os.path.isfile(path):
        issues = analyze_file(path)
    else:
        print(f"Error: {path} is neither a file nor a directory")
        sys.exit(1)

    print_issues(issues)
