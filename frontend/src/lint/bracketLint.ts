export interface LintMarker {
  startLineNumber: number;
  startColumn: number;
  endLineNumber: number;
  endColumn: number;
  message: string;
}

const PAIRS: Record<string, string> = { ")": "(", "]": "[", "}": "{" };
const OPENERS = new Set(["(", "[", "{"]);

/**
 * Not a real parser — C++/Java need an actual compiler front-end for that,
 * which isn't feasible to run client-side. This catches the most common
 * typo class (mismatched/unclosed brackets, unterminated string literals)
 * so the editor isn't silent on obvious mistakes while a real syntax error
 * only surfaces after a submission comes back COMPILE_ERROR.
 */
export function lintBrackets(source: string): LintMarker[] {
  const markers: LintMarker[] = [];
  const stack: { char: string; line: number; col: number }[] = [];
  const lines = source.split("\n");

  let inLineComment = false;
  let inBlockComment = false;
  let inString: string | null = null;

  for (let lineIdx = 0; lineIdx < lines.length; lineIdx++) {
    const line = lines[lineIdx];
    inLineComment = false;

    for (let col = 0; col < line.length; col++) {
      const ch = line[col];
      const next = line[col + 1];

      if (inLineComment) break;

      if (inBlockComment) {
        if (ch === "*" && next === "/") {
          inBlockComment = false;
          col++;
        }
        continue;
      }

      if (inString) {
        if (ch === "\\") {
          col++; // skip escaped char
          continue;
        }
        if (ch === inString) inString = null;
        continue;
      }

      if (ch === "/" && next === "/") {
        inLineComment = true;
        continue;
      }
      if (ch === "/" && next === "*") {
        inBlockComment = true;
        col++;
        continue;
      }
      if (ch === '"' || ch === "'") {
        inString = ch;
        continue;
      }

      if (OPENERS.has(ch)) {
        stack.push({ char: ch, line: lineIdx + 1, col: col + 1 });
      } else if (ch in PAIRS) {
        const top = stack[stack.length - 1];
        if (!top || top.char !== PAIRS[ch]) {
          markers.push({
            startLineNumber: lineIdx + 1,
            startColumn: col + 1,
            endLineNumber: lineIdx + 1,
            endColumn: col + 2,
            message: top
              ? `Unexpected '${ch}' — does not match the most recent open '${top.char}' from line ${top.line}.`
              : `Unexpected '${ch}' with no matching open bracket.`,
          });
        } else {
          stack.pop();
        }
      }
    }

    if (inString && !inBlockComment) {
      markers.push({
        startLineNumber: lineIdx + 1,
        startColumn: line.length,
        endLineNumber: lineIdx + 1,
        endColumn: line.length + 1,
        message: "Unterminated string literal.",
      });
      inString = null;
    }
  }

  for (const unclosed of stack) {
    markers.push({
      startLineNumber: unclosed.line,
      startColumn: unclosed.col,
      endLineNumber: unclosed.line,
      endColumn: unclosed.col + 1,
      message: `Unclosed '${unclosed.char}' — never matched by a closing bracket.`,
    });
  }

  return markers;
}
