"""SDK starter templates for multi-language Vectrion custom plugins.

Each template shows how to:
  1. Read vault metadata from stdin as JSON
  2. Scan files in vault_dir using vault_index entries
  3. Write a findings result dict to stdout as JSON

The vault_index is a list of dicts with at least:
  filename      — stored filename on disk (may be renamed for safety)
  original_name — the original uploaded filename (use for display / source_file)
  sha256        — hex digest of file contents
  size_bytes    — file size

Plugins should prefer the extracted text file (<filename>.txt) when it
exists, and fall back to the raw file (<filename>).
"""
from __future__ import annotations

import io
import json
import zipfile

# ─────────────────────────────────────────────────────────────────────────────
# plugin.json manifest template
# ─────────────────────────────────────────────────────────────────────────────

MANIFEST_TEMPLATE = """\
{
  "id": "my-custom-scanner",
  "name": "My Custom Scanner",
  "version": "1.0.0",
  "language": "LANGUAGE",
  "entry": "ENTRY",
  "description": "Describe what this scanner detects.",
  "tags": ["custom"],
  "author": ""
}
"""

# ─────────────────────────────────────────────────────────────────────────────
# Python SDK template
# ─────────────────────────────────────────────────────────────────────────────

PYTHON_TEMPLATE = '''\
#!/usr/bin/env python3
"""Vectrion custom scanner — Python subprocess plugin.

Run:  python3 scanner.py  (Vectrion pipes vault JSON to stdin)

Output: single JSON object to stdout matching the findings schema.
"""
import hashlib
import json
import re
import sys
from pathlib import Path


SCANNER_NAME = "My Python Scanner"

# Map rule_name -> (compiled regex, severity)
PATTERNS = {
    "example_api_key": (
        re.compile(r\'(?i)api[-_]?key\\s*[=:]\\s*["\\\']?([A-Za-z0-9_\\-]{20,50})\'),
        "high",
    ),
}


def scan_text(text: str, source: str) -> list[dict]:
    findings = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for rule, (pat, sev) in PATTERNS.items():
            for m in pat.finditer(line):
                findings.append({
                    "detector":    rule,
                    "severity":    sev,
                    "source_file": source,
                    "line":        line_no,
                    "secret_hash": hashlib.sha256(m.group(0).encode()).hexdigest()[:12],
                    "method":      "regex",
                })
    return findings


def main():
    payload = json.load(sys.stdin)
    vault_dir = Path(payload["vault_dir"])
    vault_index = payload["vault_index"]   # list[dict]

    all_findings, files_scanned = [], []

    for entry in vault_index:
        filename = entry.get("filename", "")
        label = entry.get("original_name", filename)
        # prefer extracted .txt, fall back to raw file
        txt_path = vault_dir / (filename + ".txt")
        raw_path = vault_dir / filename
        path = txt_path if txt_path.exists() else raw_path
        if not path.exists():
            continue
        files_scanned.append(label)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        all_findings.extend(scan_text(text, label))

    sev_counts: dict[str, int] = {}
    for f in all_findings:
        sev_counts[f["severity"]] = sev_counts.get(f["severity"], 0) + 1

    print(json.dumps({
        "scanner_name":    SCANNER_NAME,
        "findings":        all_findings,
        "files_scanned":   files_scanned,
        "total_findings":  len(all_findings),
        "severity_counts": sev_counts,
        "critical_count":  sev_counts.get("critical", 0),
        "high_count":      sev_counts.get("high", 0),
        "medium_count":    sev_counts.get("medium", 0),
        "method":          "subprocess",
    }))


if __name__ == "__main__":
    main()
'''

# ─────────────────────────────────────────────────────────────────────────────
# Node.js SDK template
# ─────────────────────────────────────────────────────────────────────────────

NODE_TEMPLATE = '''\
#!/usr/bin/env node
/**
 * Vectrion custom scanner — Node.js subprocess plugin.
 *
 * Run:  node scanner.js  (Vectrion pipes vault JSON to stdin)
 * Output: single JSON object to stdout matching the findings schema.
 */

const fs   = require(\'fs\');
const path = require(\'path\');
const crypto = require(\'crypto\');

const SCANNER_NAME = \'My Node.js Scanner\';

// Map rule_name -> { pattern: RegExp, severity: string }
const PATTERNS = {
  example_api_key: { pattern: /api[-_]?key\\s*[=:]\\s*["\\']?([A-Za-z0-9_\\-]{20,50})/gi, severity: \'high\' },
};

function scanText(text, source) {
  const findings = [];
  const lines = text.split(\'\\n\');
  for (let i = 0; i < lines.length; i++) {
    for (const [rule, { pattern, severity }] of Object.entries(PATTERNS)) {
      pattern.lastIndex = 0;
      let m;
      while ((m = pattern.exec(lines[i])) !== null) {
        findings.push({
          detector:    rule,
          severity,
          source_file: source,
          line:        i + 1,
          secret_hash: crypto.createHash(\'sha256\').update(m[0]).digest(\'hex\').slice(0, 12),
          method:      \'regex\',
        });
      }
    }
  }
  return findings;
}

let raw = \'\';
process.stdin.setEncoding(\'utf8\');
process.stdin.on(\'data\', chunk => { raw += chunk; });
process.stdin.on(\'end\', () => {
  const { vault_dir, vault_index } = JSON.parse(raw);
  const allFindings = [];
  const filesScanned = [];

  for (const entry of vault_index) {
    const filename = entry.filename || \'\';
    const label    = entry.original_name || filename;
    const txtPath  = path.join(vault_dir, filename + \'.txt\');
    const rawPath  = path.join(vault_dir, filename);
    const filePath = fs.existsSync(txtPath) ? txtPath : rawPath;
    if (!fs.existsSync(filePath)) continue;
    filesScanned.push(label);
    let text;
    try { text = fs.readFileSync(filePath, \'utf8\'); } catch { continue; }
    allFindings.push(...scanText(text, label));
  }

  const sevCounts = {};
  for (const f of allFindings) sevCounts[f.severity] = (sevCounts[f.severity] || 0) + 1;

  process.stdout.write(JSON.stringify({
    scanner_name:    SCANNER_NAME,
    findings:        allFindings,
    files_scanned:   filesScanned,
    total_findings:  allFindings.length,
    severity_counts: sevCounts,
    critical_count:  sevCounts.critical || 0,
    high_count:      sevCounts.high     || 0,
    medium_count:    sevCounts.medium   || 0,
    method:          \'subprocess\',
  }) + \'\\n\');
});
'''

# ─────────────────────────────────────────────────────────────────────────────
# Java SDK template (source — compile to scanner.jar before use)
# ─────────────────────────────────────────────────────────────────────────────

JAVA_TEMPLATE = '''\
// Vectrion custom scanner — Java subprocess plugin
//
// Compile:
//   javac Scanner.java
//   jar cfe scanner.jar Scanner Scanner.class
//
// plugin.json entry must be "scanner.jar"
// Vectrion runs: java -jar scanner.jar  (pipes vault JSON to stdin)

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.regex.*;
import org.json.*;   // Add org.json to your classpath or use a bundled JSON library

public class Scanner {
    private static final String SCANNER_NAME = "My Java Scanner";

    // rule_name -> { pattern, severity }
    private static final Map<String, String[]> PATTERNS = new LinkedHashMap<>();
    static {
        PATTERNS.put("example_api_key", new String[]{
            "(?i)api[-_]?key\\\\s*[=:]\\\\s*[\"\\\\\'']?([A-Za-z0-9_\\\\-]{20,50})", "high"
        });
    }

    public static void main(String[] args) throws Exception {
        String input = new String(System.in.readAllBytes(), StandardCharsets.UTF_8);
        JSONObject payload    = new JSONObject(input);
        String     vaultDir   = payload.getString("vault_dir");
        JSONArray  vaultIndex = payload.getJSONArray("vault_index");

        List<JSONObject> allFindings  = new ArrayList<>();
        List<String>     filesScanned = new ArrayList<>();

        for (int i = 0; i < vaultIndex.length(); i++) {
            JSONObject entry    = vaultIndex.getJSONObject(i);
            String     filename = entry.optString("filename", "");
            String     label    = entry.optString("original_name", filename);
            Path txtPath = Paths.get(vaultDir, filename + ".txt");
            Path rawPath = Paths.get(vaultDir, filename);
            Path filePath = Files.exists(txtPath) ? txtPath : rawPath;
            if (!Files.exists(filePath)) continue;
            filesScanned.add(label);
            String text;
            try { text = Files.readString(filePath, StandardCharsets.UTF_8); }
            catch (IOException e) { continue; }
            allFindings.addAll(scanText(text, label));
        }

        Map<String, Integer> sevCounts = new LinkedHashMap<>();
        for (JSONObject f : allFindings) {
            String sev = f.getString("severity");
            sevCounts.merge(sev, 1, Integer::sum);
        }

        JSONObject result = new JSONObject();
        result.put("scanner_name",    SCANNER_NAME);
        result.put("findings",        new JSONArray(allFindings));
        result.put("files_scanned",   new JSONArray(filesScanned));
        result.put("total_findings",  allFindings.size());
        result.put("severity_counts", new JSONObject(sevCounts));
        result.put("critical_count",  sevCounts.getOrDefault("critical", 0));
        result.put("high_count",      sevCounts.getOrDefault("high", 0));
        result.put("medium_count",    sevCounts.getOrDefault("medium", 0));
        result.put("method",          "subprocess");
        System.out.println(result.toString());
    }

    private static List<JSONObject> scanText(String text, String source) {
        List<JSONObject> findings = new ArrayList<>();
        String[] lines = text.split("\\n");
        for (int lineNo = 0; lineNo < lines.length; lineNo++) {
            for (Map.Entry<String, String[]> e : PATTERNS.entrySet()) {
                Pattern pat = Pattern.compile(e.getValue()[0]);
                Matcher m   = pat.matcher(lines[lineNo]);
                while (m.find()) {
                    JSONObject f = new JSONObject();
                    f.put("detector",    e.getKey());
                    f.put("severity",    e.getValue()[1]);
                    f.put("source_file", source);
                    f.put("line",        lineNo + 1);
                    f.put("secret_hash", sha256hex(m.group(0)).substring(0, 12));
                    f.put("method",      "regex");
                    findings.add(f);
                }
            }
        }
        return findings;
    }

    private static String sha256hex(String s) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] b = md.digest(s.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (byte x : b) sb.append(String.format("%02x", x));
            return sb.toString();
        } catch (Exception e) { return "000000000000"; }
    }
}
'''

# ─────────────────────────────────────────────────────────────────────────────
# Bash SDK template
# ─────────────────────────────────────────────────────────────────────────────

BASH_TEMPLATE = '''\
#!/usr/bin/env bash
# Vectrion custom scanner — Bash subprocess plugin
#
# Vectrion pipes vault JSON to stdin.
# Output: single JSON object to stdout matching the findings schema.
#
# Requires: python3 (for JSON parsing) or jq if preferred.

set -euo pipefail

SCANNER_NAME="My Bash Scanner"

# Read entire stdin
INPUT="$(cat)"

VAULT_DIR="$(printf \'%s\' "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin)[\'vault_dir\'])")"
FILE_COUNT="$(printf \'%s\' "$INPUT" | python3 -c "import json,sys; print(len(json.load(sys.stdin)[\'vault_index\']))")"

ALL_FINDINGS=\'[]\'
FILES_SCANNED=\'[]\'

# Iterate vault_index entries via python3 (bash JSON parsing is fragile)
while IFS=$\'\\t\' read -r filename original_name; do
    txt_path="${VAULT_DIR}/${filename}.txt"
    raw_path="${VAULT_DIR}/${filename}"
    if [[ -f "$txt_path" ]]; then
        scan_path="$txt_path"
    elif [[ -f "$raw_path" ]]; then
        scan_path="$raw_path"
    else
        continue
    fi

    FILES_SCANNED="$(python3 -c "
import json, sys
arr = json.loads(sys.argv[1])
arr.append(sys.argv[2])
print(json.dumps(arr))
" "$FILES_SCANNED" "$original_name")"

    # TODO: Add your grep/awk/regex scanning logic here.
    # Example: search for bearer tokens
    while IFS= read -r match; do
        [[ -z "$match" ]] && continue
        HASH="$(printf \'%s\' "$match" | sha256sum | cut -c1-12)"
        LINENUM="$(grep -n "$match" "$scan_path" 2>/dev/null | head -1 | cut -d: -f1 || echo 0)"
        FINDING=$(python3 -c "import json; print(json.dumps({
            \'detector\': \'bearer_token\',
            \'severity\': \'high\',
            \'source_file\': \'$original_name\',
            \'line\': int(\'${LINENUM:-0}\'),
            \'secret_hash\': \'$HASH\',
            \'method\': \'regex\'
        }))")
        ALL_FINDINGS="$(python3 -c "
import json,sys
arr=json.loads(sys.argv[1]); arr.append(json.loads(sys.argv[2])); print(json.dumps(arr))
" "$ALL_FINDINGS" "$FINDING")"
    done < <(grep -oP \'(?i)Bearer\\s+\\K[A-Za-z0-9_.\\-]{20,200}\' "$scan_path" 2>/dev/null || true)

done < <(printf \'%s\' "$INPUT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for e in data[\'vault_index\']:
    print(e.get(\'filename\',\'\') + \'\\t\' + e.get(\'original_name\', e.get(\'filename\',\'\')))
")

python3 -c "
import json, sys

findings     = json.loads(sys.argv[1])
files_scanned = json.loads(sys.argv[2])
scanner_name  = sys.argv[3]

sev_counts = {}
for f in findings:
    sev_counts[f[\'severity\']] = sev_counts.get(f[\'severity\'], 0) + 1

print(json.dumps({
    \'scanner_name\':    scanner_name,
    \'findings\':        findings,
    \'files_scanned\':   files_scanned,
    \'total_findings\':  len(findings),
    \'severity_counts\': sev_counts,
    \'critical_count\':  sev_counts.get(\'critical\', 0),
    \'high_count\':      sev_counts.get(\'high\', 0),
    \'medium_count\':    sev_counts.get(\'medium\', 0),
    \'method\':          \'subprocess\',
}))
" "$ALL_FINDINGS" "$FILES_SCANNED" "$SCANNER_NAME"
'''

# ─────────────────────────────────────────────────────────────────────────────
# Go SDK template (source — compile before use)
# ─────────────────────────────────────────────────────────────────────────────

GO_TEMPLATE = '''\
// Vectrion custom scanner — Go subprocess plugin
//
// Compile:  go build -o scanner main.go
// plugin.json entry must be "./scanner"
// Vectrion runs: ./scanner  (pipes vault JSON to stdin)

package main

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

const ScannerName = "My Go Scanner"

type Finding struct {
	Detector   string `json:"detector"`
	Severity   string `json:"severity"`
	SourceFile string `json:"source_file"`
	Line       int    `json:"line"`
	SecretHash string `json:"secret_hash"`
	Method     string `json:"method"`
}

type Result struct {
	ScannerName    string            `json:"scanner_name"`
	Findings       []Finding         `json:"findings"`
	FilesScanned   []string          `json:"files_scanned"`
	TotalFindings  int               `json:"total_findings"`
	SeverityCounts map[string]int    `json:"severity_counts"`
	CriticalCount  int               `json:"critical_count"`
	HighCount      int               `json:"high_count"`
	MediumCount    int               `json:"medium_count"`
	Method         string            `json:"method"`
}

type VaultEntry struct {
	Filename     string `json:"filename"`
	OriginalName string `json:"original_name"`
}

type Payload struct {
	VaultDir   string       `json:"vault_dir"`
	VaultIndex []VaultEntry `json:"vault_index"`
}

// patterns maps rule name -> (regex, severity)
var patterns = []struct {
	name     string
	re       *regexp.Regexp
	severity string
}{
	{"example_api_key", regexp.MustCompile(`(?i)api[-_]?key\\s*[=:]\\s*["\\']?([A-Za-z0-9_\\-]{20,50})`), "high"},
}

func sha256hex(s string) string {
	h := sha256.Sum256([]byte(s))
	return fmt.Sprintf("%x", h)
}

func scanText(text, source string) []Finding {
	var findings []Finding
	lines := strings.Split(text, "\\n")
	for i, line := range lines {
		for _, p := range patterns {
			matches := p.re.FindAllString(line, -1)
			for _, m := range matches {
				findings = append(findings, Finding{
					Detector:   p.name,
					Severity:   p.severity,
					SourceFile: source,
					Line:       i + 1,
					SecretHash: sha256hex(m)[:12],
					Method:     "regex",
				})
			}
		}
	}
	return findings
}

func main() {
	var payload Payload
	if err := json.NewDecoder(os.Stdin).Decode(&payload); err != nil {
		fmt.Fprintf(os.Stderr, "failed to decode stdin: %v\\n", err)
		os.Exit(1)
	}

	var allFindings []Finding
	var filesScanned []string

	for _, entry := range payload.VaultIndex {
		label := entry.OriginalName
		if label == "" {
			label = entry.Filename
		}
		txtPath := filepath.Join(payload.VaultDir, entry.Filename+".txt")
		rawPath := filepath.Join(payload.VaultDir, entry.Filename)
		var scanPath string
		if _, err := os.Stat(txtPath); err == nil {
			scanPath = txtPath
		} else if _, err := os.Stat(rawPath); err == nil {
			scanPath = rawPath
		} else {
			continue
		}
		data, err := os.ReadFile(scanPath)
		if err != nil {
			continue
		}
		filesScanned = append(filesScanned, label)
		allFindings = append(allFindings, scanText(string(data), label)...)
	}

	sevCounts := map[string]int{}
	for _, f := range allFindings {
		sevCounts[f.Severity]++
	}
	if allFindings == nil {
		allFindings = []Finding{}
	}
	if filesScanned == nil {
		filesScanned = []string{}
	}

	result := Result{
		ScannerName:    ScannerName,
		Findings:       allFindings,
		FilesScanned:   filesScanned,
		TotalFindings:  len(allFindings),
		SeverityCounts: sevCounts,
		CriticalCount:  sevCounts["critical"],
		HighCount:      sevCounts["high"],
		MediumCount:    sevCounts["medium"],
		Method:         "subprocess",
	}
	if err := json.NewEncoder(os.Stdout).Encode(result); err != nil {
		fmt.Fprintf(os.Stderr, "failed to encode result: %v\\n", err)
		os.Exit(1)
	}
}
'''

# ─────────────────────────────────────────────────────────────────────────────
# SDK zip builder
# ─────────────────────────────────────────────────────────────────────────────

_LANG_CONFIGS = {
    "python": {"source": PYTHON_TEMPLATE, "source_file": "scanner.py",  "entry": "scanner.py"},
    "node":   {"source": NODE_TEMPLATE,   "source_file": "scanner.js",  "entry": "scanner.js"},
    "java":   {"source": JAVA_TEMPLATE,   "source_file": "Scanner.java","entry": "scanner.jar"},
    "bash":   {"source": BASH_TEMPLATE,   "source_file": "scanner.sh",  "entry": "scanner.sh"},
    "go":     {"source": GO_TEMPLATE,     "source_file": "main.go",     "entry": "./scanner"},
}


def get_sdk_zip(language: str) -> io.BytesIO:
    """Return a BytesIO zip containing plugin.json + the scanner source file.

    Raises ValueError for unsupported languages.
    """
    cfg = _LANG_CONFIGS.get(language)
    if cfg is None:
        raise ValueError(f"No SDK template for language: {language!r}")

    manifest = (
        MANIFEST_TEMPLATE
        .replace("LANGUAGE", language)
        .replace("ENTRY", cfg["entry"])
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("plugin.json", manifest)
        zf.writestr(cfg["source_file"], cfg["source"])
    buf.seek(0)
    return buf
