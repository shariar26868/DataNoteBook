# Requirements Document

## Introduction

This document describes the functional requirements for the DataNotebook UI redesign. The redesign transforms the existing single-page data analysis frontend (plain HTML/CSS/JS, no build step) from a basic two-column form+results dashboard into a polished, two-mode application. The two distinct modes are:

1. **Welcome Screen** — shown before any dataset is loaded; provides greeting, dynamic suggestion chips, and file upload with integrated chat input.
2. **Notebook+Chat Layout** — shown after a dataset is uploaded; provides a notebook canvas (left) and a chat sidebar (right) with streaming code execution and an action bar.

All state transitions occur within a single `index.html` file using vanilla JavaScript. No page navigations occur — views are shown/hidden via CSS classes managed by a lightweight state object.

---

## Glossary

- **App**: The single-page DataNotebook frontend application (`index.html`).
- **Welcome_Screen**: The `#welcome-screen` view rendered when no active dataset session exists.
- **Notebook_Layout**: The `#notebook-layout` view rendered when an active dataset session exists.
- **Session**: An active backend session established by a successful `/api/upload` response; persisted via an httpOnly cookie.
- **Session_State**: The in-memory JavaScript object tracking session metadata, conversation history, and pending code.
- **Chip**: A `button.chip` suggestion element rendered below the greeting after a dataset is uploaded.
- **Action_Bar**: The `.action-bar` element containing "Accept & Run", "Accept", and "Cancel" buttons, shown when `pendingCode` is non-null.
- **Pending_Code**: The `sessionState.pendingCode` field; the AI-generated code from the latest AI turn that has not yet been acted upon.
- **Notebook_Cell**: A `.notebook-cell` element containing a code block (`.cell-source`) and output area (`.cell-output`).
- **Chat_Sidebar**: The `.chat-sidebar` right panel containing message history, action bar, and input.
- **SSE**: Server-Sent Events stream returned by `POST /api/execute/stream`.
- **Status_Bar**: The `#status-bar` transient notification banner at the top of the page.
- **Chip_Generator**: The client-side `generateChips(columns, dtypes, dfName)` function.
- **Df_Name_Inferrer**: The client-side `inferDfName(filename)` function.
- **SSE_Parser**: The client-side `parseSSELine(rawLine)` function.
- **Explanation_Formatter**: The client-side `formatExplanation(text)` function.

---

## Requirements

### Requirement 1: Application State and Screen Management

**User Story:** As a user, I want the application to automatically show the right screen based on whether I have an active session, so that I am never shown an empty notebook with no dataset.

#### Acceptance Criteria

1. WHEN the page loads and no active Session exists, THE App SHALL render the Welcome_Screen and hide the Notebook_Layout.
2. WHEN the page loads and an active Session exists (session cookie present), THE App SHALL render the Notebook_Layout and hide the Welcome_Screen.
3. WHEN a file upload succeeds and a Session is established, THE App SHALL hide the Welcome_Screen and render the Notebook_Layout.
4. WHEN the user clicks the "+ New Chat" button, THE App SHALL clear the Session_State client-side and render the Welcome_Screen, hiding the Notebook_Layout.
5. THE App SHALL manage all screen transitions without page navigation, using CSS class changes only.

---

### Requirement 2: Welcome Screen — Greeting and Layout

**User Story:** As a user, I want to see a friendly greeting and clear entry point when I first open the application, so that I immediately understand what to do.

#### Acceptance Criteria

1. THE Welcome_Screen SHALL display a heading greeting (e.g., "Hello, User") inside a `.greeting-area` element.
2. THE Welcome_Screen SHALL display a subtitle (e.g., "How can I help you today?") below the heading.
3. THE Welcome_Screen SHALL render a `.welcome-input-bar` containing a file attach button (`#attach-btn`), a hidden file input (`#welcome-file`), a textarea (`#welcome-msg`), and a send button (`#welcome-send`).
4. THE Welcome_Screen SHALL display an `.upload-hint` element below the input bar showing instructional text ("Upload a dataset to get started") when no dataset has been uploaded.

---

### Requirement 3: Welcome Screen — File Upload

**User Story:** As a user, I want to upload a CSV or XLSX file from the Welcome Screen, so that I can start analysing my dataset.

#### Acceptance Criteria

1. WHEN the user clicks the `#attach-btn`, THE Welcome_Screen SHALL open a file picker restricted to `.csv,.xlsx,.xls` file types.
2. WHEN the user selects a valid file and it is submitted, THE App SHALL send a `POST /api/upload` multipart request with `credentials: 'include'`.
3. WHEN `/api/upload` returns a 2xx response, THE App SHALL store the returned `filename`, `columns`, `dtypes`, `row_count`, and inferred `dfName` into Session_State.
4. IF `/api/upload` returns a non-2xx response, THEN THE Welcome_Screen SHALL display the error detail in the `.upload-hint` element and keep the Welcome_Screen visible.
5. WHEN no file is selected and the user attempts to send a message, THE Welcome_Screen SHALL display "Upload a dataset first" in the `.upload-hint` element and apply a shake animation to the input bar.

---

### Requirement 4: Welcome Screen — Suggestion Chips

**User Story:** As a user, I want to see relevant suggested prompts after uploading my dataset, so that I can quickly start exploring it without having to think of questions.

#### Acceptance Criteria

1. WHEN a dataset upload succeeds, THE Chip_Generator SHALL generate between 1 and 4 suggestion Chips from the returned `columns`, `dtypes`, and `dfName`.
2. THE Chip_Generator SHALL always include a chip with text "Show summary statistics for {dfName}".
3. WHEN a numeric column exists in the dataset, THE Chip_Generator SHALL include a chip with text "Visualize the distribution of '{col}'" for the first numeric column found.
4. WHEN a categorical column exists in the dataset, THE Chip_Generator SHALL include a chip with text "Show value counts for '{col}'" for the first categorical column found.
5. WHEN both a numeric column and a categorical column exist, THE Chip_Generator SHALL include a chip with text "Create a plot comparing {numCol} by '{catCol}'".
6. THE Chip_Generator SHALL render at most 4 Chips regardless of the number of columns present.
7. WHEN the user clicks a Chip, THE Welcome_Screen SHALL populate the `#welcome-msg` textarea with the chip's prompt text and focus the textarea.

---

### Requirement 5: Welcome Screen — First Message Send

**User Story:** As a user, I want to send my first message (or click a chip) from the Welcome Screen and be taken directly into the notebook, so that my workflow is seamless.

#### Acceptance Criteria

1. WHEN the user types a message in `#welcome-msg` and clicks `#welcome-send` (or presses Enter), THE App SHALL transition to the Notebook_Layout with the typed message pre-loaded as the first user message.
2. WHEN a Chip is clicked and the user subsequently clicks `#welcome-send`, THE App SHALL use the chip's prompt text as the first message.
3. WHEN `#welcome-send` is clicked with an empty textarea and no active Session, THE Welcome_Screen SHALL display a validation hint and not transition to Notebook_Layout.

---

### Requirement 6: Notebook+Chat Layout — Structure

**User Story:** As a user, I want a split-panel view with my notebook on the left and a chat sidebar on the right, so that I can see code cells and the conversation simultaneously.

#### Acceptance Criteria

1. THE Notebook_Layout SHALL render a `.notebook-area` left panel and a `.chat-sidebar` right panel fixed at 320px width.
2. THE Chat_Sidebar SHALL contain a `.sidebar-header`, a `.messages-list`, an `.action-bar`, and a `.sidebar-input-bar`.
3. THE `.sidebar-header` SHALL display the dataset filename (from Session_State) and include a "+ New Chat" button (`#new-chat-btn`), an options button (`#menu-btn`), and a close button (`#close-sidebar`).
4. WHEN the user clicks `#close-sidebar`, THE Notebook_Layout SHALL collapse the Chat_Sidebar and expand the `.notebook-area` to full width.
5. THE `.messages-list` SHALL be scrollable via `overflow-y: auto` with a fixed height so that long conversations do not reflow the page.

---

### Requirement 7: Chat — Sending Messages and Receiving AI Responses

**User Story:** As a user, I want to send questions about my dataset in the chat sidebar and receive AI explanations with optional code, so that I can explore my data interactively.

#### Acceptance Criteria

1. WHEN the user types a message in `#sidebar-msg` and clicks `#sidebar-send`, THE App SHALL append a `.msg-bubble.user` to `.messages-list` and send `POST /api/chat` with `{ message }` and `credentials: 'include'`.
2. WHEN `/api/chat` returns a response, THE App SHALL append a `.msg-bubble.ai` to `.messages-list` containing a `.msg-explanation` element with the explanation text.
3. WHEN the AI response contains code, THE App SHALL set `sessionState.pendingCode` to the returned code and render the Action_Bar.
4. WHEN `/api/chat` returns 401 or 404, THE App SHALL display a Status_Bar banner reading "Session expired — please re-upload your dataset" and transition to the Welcome_Screen.
5. THE App SHALL preserve all messages in `sessionState.messages` across sends within the same Session.
6. WHEN the AI explanation contains backtick-delimited spans, THE Explanation_Formatter SHALL wrap each span in a styled `.code-ref` element rather than rendering raw backtick characters.

---

### Requirement 8: Action Bar — Pending Code Management

**User Story:** As a user, I want clear action buttons to decide what to do with AI-generated code, so that I stay in control of what gets executed in my notebook.

#### Acceptance Criteria

1. THE Action_Bar SHALL be visible if and only if `sessionState.pendingCode` is non-null.
2. WHEN `sessionState.pendingCode` is set to null, THE App SHALL hide the Action_Bar immediately.
3. WHEN the user clicks "Accept & Run", THE App SHALL append a Notebook_Cell to `.cell-list`, call `POST /api/execute/stream` with the pending code, stream output into the cell's `.cell-output`, and then set `sessionState.pendingCode` to null.
4. WHEN the user clicks "Accept", THE App SHALL append a Notebook_Cell with the pending code and set `sessionState.pendingCode` to null without executing.
5. WHEN the user clicks "Cancel", THE App SHALL set `sessionState.pendingCode` to null and hide the Action_Bar without appending any cell.
6. WHEN a second chat message is sent before the user acts on a pending code, THE App SHALL discard the previous Pending_Code, hide the Action_Bar, and display the Action_Bar reflecting only the latest AI response's code.

---

### Requirement 9: Notebook Area — Cell Rendering and Ordering

**User Story:** As a user, I want my accepted code and its output displayed as ordered notebook cells, so that I have a clear record of my analysis steps.

#### Acceptance Criteria

1. THE `.notebook-area` SHALL render an ordered `.cell-list` of Notebook_Cells.
2. WHEN a cell is appended, THE Notebook_Cell SHALL contain a `.cell-source` block with the code text and a `.cell-output` area for output.
3. THE App SHALL append cells in the order that "Accept" or "Accept & Run" actions are taken; no existing cell SHALL be removed by the system.
4. WHEN "Accept & Run" is triggered, THE `.cell-output` SHALL be updated incrementally as SSE events are received, with `scrollTop` set to `scrollHeight` after each append.

---

### Requirement 10: SSE Streaming Execution

**User Story:** As a user, I want to see code output appear live as it streams from the backend, so that I get immediate feedback without waiting for the full execution to finish.

#### Acceptance Criteria

1. WHEN `POST /api/execute/stream` is called, THE App SHALL read the SSE stream using `ReadableStream` and process each complete `data:` event.
2. WHEN an SSE event of type `"stdout"` is received, THE App SHALL append the event's `data` text to the `.cell-output` `<pre>` element.
3. WHEN an SSE event of type `"image"` is received (base64 data URI), THE App SHALL insert an `<img>` element with the data URI as `src` into the `.cell-output` area without a second fetch.
4. WHEN an SSE event of type `"table"` is received, THE App SHALL render an HTML `<table>` from the event's `data` array into the `.cell-output` area.
5. WHEN an SSE event of type `"error"` is received, THE App SHALL display the error text in the `.cell-output` area with error styling (red colour) and append a log entry.
6. WHEN an SSE event of type `"done"` is received, THE App SHALL process it exactly once and ignore any subsequent `"done"` events for the same stream.
7. IF the streaming request itself fails (network error or non-2xx), THEN THE App SHALL display the error message in the `.cell-output` area with error styling.

---

### Requirement 11: Status Bar Notifications

**User Story:** As a user, I want to see brief, non-intrusive status messages for background operations, so that I always know what the application is doing.

#### Acceptance Criteria

1. THE Status_Bar SHALL be a single-line banner rendered at the top of the page.
2. WHEN a transient status message is set, THE Status_Bar SHALL display the message and automatically fade out after 4 seconds.
3. THE Status_Bar SHALL be used for upload progress, session expiry notices, and other transient state changes.

---

### Requirement 12: Df Name Inference

**User Story:** As a developer, I want the application to infer a valid Python variable name from an uploaded filename, so that generated code references a consistent, valid identifier for the dataframe.

#### Acceptance Criteria

1. WHEN a file is uploaded, THE Df_Name_Inferrer SHALL derive a `dfName` from the filename (e.g., `"titanic.csv"` → `"df_titanic"`).
2. THE Df_Name_Inferrer SHALL produce a valid Python identifier for any non-empty filename input.
3. THE Df_Name_Inferrer SHALL store the resulting `dfName` in Session_State for use in Chip generation and API calls.

---

### Requirement 13: SSE Parsing Robustness

**User Story:** As a developer, I want the SSE parser to handle malformed or unexpected input without throwing, so that a single bad event does not break the streaming output.

#### Acceptance Criteria

1. THE SSE_Parser SHALL parse valid `data:` SSE lines into structured event objects.
2. IF a raw SSE line is malformed or cannot be parsed as JSON, THEN THE SSE_Parser SHALL skip that event and continue processing without throwing an exception.
3. THE SSE_Parser SHALL handle arbitrary string input (including empty strings, non-SSE lines, and binary-safe strings) without throwing.

---

### Requirement 14: Security and XSS Prevention

**User Story:** As a security-conscious developer, I want all user-controlled strings to be inserted safely, so that the application is not vulnerable to cross-site scripting attacks.

#### Acceptance Criteria

1. THE App SHALL assign all user-controlled strings (filename, column names, message text, AI explanation text) via `.textContent` or equivalent safe DOM APIs.
2. THE App SHALL never assign user-controlled strings via `.innerHTML` or `document.write`.
3. THE App SHALL send all API requests with `credentials: 'include'` so the httpOnly session cookie is included automatically.
4. THE App SHALL restrict file inputs to `.csv,.xlsx,.xls` via the `accept` attribute on file input elements.

---

### Requirement 15: Accessibility and Responsive Layout

**User Story:** As a user on different devices, I want the interface to be usable and readable at various screen sizes, so that I can use DataNotebook on a laptop or a smaller screen.

#### Acceptance Criteria

1. THE App SHALL use semantic HTML elements (`<header>`, `<main>`, `<button>`, `<textarea>`) with appropriate ARIA roles where native semantics are insufficient.
2. WHEN the viewport width is below 900px, THE Notebook_Layout SHALL stack the `.notebook-area` and `.chat-sidebar` vertically rather than side-by-side.
3. THE App SHALL provide visible focus indicators on all interactive elements (`:focus-visible` styling).
4. WHILE a file upload or API request is in progress, THE App SHALL disable the corresponding submit button to prevent duplicate submissions.
