"""
Comprehensive Markdown to Quill Delta Converter

Converts markdown text to Quill Delta format (JSON operations).
Supports: headers, bold, italic, strikethrough, code, links, images,
blockquotes, ordered/unordered lists, horizontal rules, and code blocks.
"""

import re
from typing import Any


class MarkdownToDelta:
    """Converts Markdown text to Quill Delta format."""

    def __init__(self):
        # Inline patterns (order matters - more specific patterns first)
        self.inline_patterns = [
            # Images: ![alt](url)
            (r'!\[([^\]]*)\]\(([^)]+)\)', self._handle_image),
            # Links: [text](url)
            (r'\[([^\]]+)\]\(([^)]+)\)', self._handle_link),
            # Bold + Italic: ***text*** or ___text___
            (r'\*\*\*(.+?)\*\*\*', lambda m: self._handle_format(m,
             {'bold': True, 'italic': True})),
            (r'___(.+?)___', lambda m: self._handle_format(m,
             {'bold': True, 'italic': True})),
            # Bold: **text** or __text__
            (r'\*\*(.+?)\*\*',
             lambda m: self._handle_format(m, {'bold': True})),
            (r'__(.+?)__', lambda m: self._handle_format(m, {'bold': True})),
            # Italic: *text* or _text_
            (r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)',
             lambda m: self._handle_format(m, {'italic': True})),
            (r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)',
             lambda m: self._handle_format(m, {'italic': True})),
            # Strikethrough: ~~text~~
            (r'~~(.+?)~~', lambda m: self._handle_format(m, {'strike': True})),
            # Inline code: `code`
            (r'`([^`]+)`', lambda m: self._handle_format(m, {'code': True})),
        ]

    def convert(self, markdown: str) -> dict[str, list[dict[str, Any]]]:
        """
        Convert markdown string to Quill Delta format.

        Args:
            markdown: The markdown text to convert

        Returns:
            A dictionary with 'ops' key containing list of delta operations
        """
        if not markdown:
            return {"ops": []}

        ops = []
        lines = markdown.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i]

            # Check for code blocks (```)
            if line.strip().startswith('```'):
                code_block_ops, lines_consumed = self._handle_code_block(
                    lines, i)
                ops.extend(code_block_ops)
                i += lines_consumed
                continue

            # Check for horizontal rule
            if self._is_horizontal_rule(line):
                ops.append({"insert": {"divider": True}})
                ops.append({"insert": "\n"})
                i += 1
                continue

            # Check for headers
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if header_match:
                level = len(header_match.group(1))
                content = header_match.group(2)
                inline_ops = self._parse_inline(content)
                ops.extend(inline_ops)
                ops.append({"insert": "\n", "attributes": {"header": level}})
                i += 1
                continue

            # Check for blockquote
            blockquote_match = re.match(r'^>\s*(.*)$', line)
            if blockquote_match:
                content = blockquote_match.group(1)
                if content:
                    inline_ops = self._parse_inline(content)
                    ops.extend(inline_ops)
                else:
                    ops.append({"insert": ""})
                ops.append(
                    {"insert": "\n", "attributes": {"blockquote": True}})
                i += 1
                continue

            # Check for unordered list
            unordered_match = re.match(r'^(\s*)[-*+]\s+(.+)$', line)
            if unordered_match:
                indent = len(unordered_match.group(1)) // 2
                content = unordered_match.group(2)
                inline_ops = self._parse_inline(content)
                ops.extend(inline_ops)
                list_attrs = {"list": "bullet"}
                if indent > 0:
                    list_attrs["indent"] = indent
                ops.append({"insert": "\n", "attributes": list_attrs})
                i += 1
                continue

            # Check for ordered list
            ordered_match = re.match(r'^(\s*)\d+\.\s+(.+)$', line)
            if ordered_match:
                indent = len(ordered_match.group(1)) // 2
                content = ordered_match.group(2)
                inline_ops = self._parse_inline(content)
                ops.extend(inline_ops)
                list_attrs = {"list": "ordered"}
                if indent > 0:
                    list_attrs["indent"] = indent
                ops.append({"insert": "\n", "attributes": list_attrs})
                i += 1
                continue

            # Check for checklist/task list
            task_match = re.match(r'^[-*+]\s+\[([ xX])\]\s+(.+)$', line)
            if task_match:
                checked = task_match.group(1).lower() == 'x'
                content = task_match.group(2)
                inline_ops = self._parse_inline(content)
                ops.extend(inline_ops)
                ops.append({
                    "insert": "\n",
                    "attributes": {"list": "checked" if checked else "unchecked"}
                })
                i += 1
                continue

            # Regular paragraph or empty line
            if line.strip():
                inline_ops = self._parse_inline(line)
                ops.extend(inline_ops)
            ops.append({"insert": "\n"})
            i += 1

        # Clean up trailing newlines if needed
        ops = self._cleanup_ops(ops)

        return {"ops": ops}

    def _parse_inline(self, text: str) -> list[dict[str, Any]]:
        """Parse inline markdown formatting and return delta operations."""
        if not text:
            return []

        # Track segments with their positions and formatting
        segments = []

        # Find all matches for all patterns
        matches = []
        for pattern, handler in self.inline_patterns:
            for match in re.finditer(pattern, text):
                matches.append({
                    'start': match.start(),
                    'end': match.end(),
                    'match': match,
                    'handler': handler
                })

        # Sort by start position, then by length (longer matches first for same start)
        matches.sort(key=lambda x: (x['start'], -(x['end'] - x['start'])))

        # Remove overlapping matches (keep earlier/longer ones)
        filtered_matches = []
        last_end = 0
        for m in matches:
            if m['start'] >= last_end:
                filtered_matches.append(m)
                last_end = m['end']

        # Build segments
        pos = 0
        for m in filtered_matches:
            # Add plain text before this match
            if m['start'] > pos:
                plain_text = text[pos:m['start']]
                if plain_text:
                    segments.append({"insert": plain_text})

            # Add the formatted segment
            result = m['handler'](m['match'])
            if isinstance(result, list):
                segments.extend(result)
            else:
                segments.append(result)

            pos = m['end']

        # Add remaining plain text
        if pos < len(text):
            remaining = text[pos:]
            if remaining:
                segments.append({"insert": remaining})

        # If no matches found, return plain text
        if not segments and text:
            segments.append({"insert": text})

        return segments

    def _handle_format(self, match: re.Match, attributes: dict) -> dict[str, Any]:
        """Handle basic formatting (bold, italic, strikethrough, code)."""
        content = match.group(1)

        # Check for nested formatting within the content
        nested_ops = self._parse_nested_inline(content, attributes)
        if len(nested_ops) > 1:
            return nested_ops

        return {"insert": content, "attributes": attributes}

    def _parse_nested_inline(self, text: str, parent_attrs: dict) -> list[dict[str, Any]]:
        """Parse nested inline formatting, merging with parent attributes."""
        # Simplified nested patterns (avoid recursive complexity)
        nested_patterns = [
            # Bold inside italic or vice versa
            (r'\*\*(.+?)\*\*', {'bold': True}),
            (r'__(.+?)__', {'bold': True}),
            (r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', {'italic': True}),
            (r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)', {'italic': True}),
            (r'~~(.+?)~~', {'strike': True}),
            (r'`([^`]+)`', {'code': True}),
        ]

        segments = []
        matches = []

        for pattern, attrs in nested_patterns:
            # Skip if parent already has this attribute
            if any(k in parent_attrs for k in attrs.keys()):
                continue
            for match in re.finditer(pattern, text):
                matches.append({
                    'start': match.start(),
                    'end': match.end(),
                    'content': match.group(1),
                    'attrs': attrs
                })

        if not matches:
            return [{"insert": text, "attributes": parent_attrs}]

        # Sort and filter overlapping
        matches.sort(key=lambda x: (x['start'], -(x['end'] - x['start'])))
        filtered = []
        last_end = 0
        for m in matches:
            if m['start'] >= last_end:
                filtered.append(m)
                last_end = m['end']

        pos = 0
        for m in filtered:
            if m['start'] > pos:
                plain = text[pos:m['start']]
                if plain:
                    segments.append(
                        {"insert": plain, "attributes": parent_attrs.copy()})

            merged_attrs = {**parent_attrs, **m['attrs']}
            segments.append(
                {"insert": m['content'], "attributes": merged_attrs})
            pos = m['end']

        if pos < len(text):
            remaining = text[pos:]
            if remaining:
                segments.append(
                    {"insert": remaining, "attributes": parent_attrs.copy()})

        return segments if segments else [{"insert": text, "attributes": parent_attrs}]

    def _handle_link(self, match: re.Match) -> dict[str, Any]:
        """Handle link: [text](url)"""
        text = match.group(1)
        url = match.group(2)
        return {"insert": text, "attributes": {"link": url}}

    def _handle_image(self, match: re.Match) -> dict[str, Any]:
        """Handle image: ![alt](url)"""
        alt = match.group(1)
        url = match.group(2)
        return {"insert": {"image": url}, "attributes": {"alt": alt} if alt else {}}

    def _handle_code_block(self, lines: list[str], start_idx: int) -> tuple[list[dict], int]:
        """Handle fenced code blocks (```)."""
        ops = []
        first_line = lines[start_idx].strip()

        # Extract language if specified
        language = None
        if len(first_line) > 3:
            language = first_line[3:].strip()

        i = start_idx + 1
        code_lines = []

        while i < len(lines):
            if lines[i].strip() == '```':
                i += 1
                break
            code_lines.append(lines[i])
            i += 1

        # Add code content
        code_content = '\n'.join(code_lines)
        if code_content:
            attrs = {"code-block": True}
            if language:
                attrs["code-block"] = language

            # For code blocks, each line needs the code-block attribute on newline
            for idx, code_line in enumerate(code_lines):
                if code_line:
                    ops.append({"insert": code_line})
                if idx < len(code_lines) - 1 or code_line:
                    code_attrs = {"code-block": language if language else True}
                    ops.append({"insert": "\n", "attributes": code_attrs})

            # Final newline for code block
            if code_lines:
                ops.append({"insert": "\n", "attributes": {
                           "code-block": language if language else True}})

        lines_consumed = i - start_idx
        return ops, lines_consumed

    def _is_horizontal_rule(self, line: str) -> bool:
        """Check if line is a horizontal rule (---, ***, ___)."""
        stripped = line.strip()
        if len(stripped) < 3:
            return False

        # Check for ---, ***, or ___
        if re.match(r'^[-]{3,}$', stripped):
            return True
        if re.match(r'^[*]{3,}$', stripped):
            return True
        if re.match(r'^[_]{3,}$', stripped):
            return True

        # Check for spaced versions: - - -, * * *, _ _ _
        if re.match(r'^[-]\s+[-]\s+[-][\s-]*$', stripped):
            return True
        if re.match(r'^[*]\s+[*]\s+[*][\s*]*$', stripped):
            return True
        if re.match(r'^[_]\s+[_]\s+[_][\s_]*$', stripped):
            return True

        return False

    def _cleanup_ops(self, ops: list[dict]) -> list[dict]:
        """Clean up and optimize operations list."""
        if not ops:
            return ops

        # Remove empty inserts (but keep newlines)
        cleaned = []
        for op in ops:
            insert = op.get("insert")
            if insert == "" and "attributes" not in op:
                continue
            cleaned.append(op)

        # Merge consecutive plain text inserts
        merged = []
        for op in cleaned:
            if (merged and
                isinstance(op.get("insert"), str) and
                isinstance(merged[-1].get("insert"), str) and
                "attributes" not in op and
                    "attributes" not in merged[-1]):
                merged[-1]["insert"] += op["insert"]
            else:
                merged.append(op)

        return merged


def convert_markdown_to_delta(markdown: str) -> dict[str, list[dict[str, Any]]]:
    """
    Convenience function to convert markdown to Quill Delta.

    Args:
        markdown: The markdown text to convert

    Returns:
        A dictionary with 'ops' key containing list of delta operations

    Example:
        >>> delta = convert_markdown_to_delta("**Hello** *World*")
        >>> print(delta)
        {'ops': [
            {'insert': 'Hello', 'attributes': {'bold': True}},
            {'insert': ' '},
            {'insert': 'World', 'attributes': {'italic': True}},
            {'insert': '\\n'}
        ]}
    """
    converter = MarkdownToDelta()
    return converter.convert(markdown)


# Alias for backwards compatibility / shorter name
md_to_delta = convert_markdown_to_delta
