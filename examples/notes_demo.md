# Demo: save_note

**Archetype:** Filesystem write

## Description to pass to `create_tool`

```
Create a tool called save_note that takes a title and content, and saves it as a markdown file in the ~/genesis_notes folder. Prepend today's date in YYYY-MM-DD format to the filename. Create the folder if it doesn't exist. Return the full path of the saved file.
```

## How to create it

In Claude Desktop:

> "Use create_tool with this description: Create a tool called save_note that takes a title and content, and saves it as a markdown file in the ~/genesis_notes folder. Prepend today's date in YYYY-MM-DD format to the filename. Create the folder if it doesn't exist. Return the full path of the saved file."

## Expected tool input

```json
{
  "title": "Meeting Notes",
  "content": "Discussed project roadmap and Q3 goals."
}
```

## Expected tool output

```json
{
  "status": "success",
  "data": {
    "file_path": "C:\\Users\\you\\genesis_notes\\2026-05-21_meeting-notes.md"
  },
  "message": "Note saved to C:\\Users\\you\\genesis_notes\\2026-05-21_meeting-notes.md"
}
```

*(Path will be OS-appropriate — `~/genesis_notes/` on macOS/Linux.)*

## What this demonstrates

- `pathlib.Path` filesystem operations
- `Path.home()` for cross-platform home directory
- Directory creation with `mkdir(parents=True, exist_ok=True)`
- `encoding="utf-8"` in `open()` calls
