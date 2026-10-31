# Filling web forms

Read this before the first browser step. The lessons come from real runs on an Adobe Acrobat Sign
"esign widget" (a PDF drawn in the page with live `<input>` overlays) and on ordinary forms. They hold
whatever browser tool you're using.

## 1. Clear the way
- Cookie banner: choose the most privacy-preserving option ("reject", "only necessary").
- A banner or dialog whose button means "I accept the terms / consent" (e.g. "Weiter" on e-sign pages) is the
  user's decision. Ask in chat, wait for a yes, then click. Never click it silently.
- Login required: ask the user to log in themselves and tell you when they're done. Never type passwords.
- Stay in the form's own tab. Don't open, read or list the user's other tabs unless they ask.

## 2. Discover the fields from the DOM
On ordinary pages an accessibility snapshot from your browser tool usually lists every field with its label. On
widget pages the document is drawn on a canvas and snapshots show little, so query the DOM with JavaScript:

```js
[...document.querySelectorAll('input,select,textarea')]
  .filter(e => e.offsetParent && e.type !== 'file')
  .map((e,i) => [i, e.tagName, e.type, e.name || e.id, e.getAttribute('aria-label') || e.placeholder || '',
                 e.type==='radio'||e.type==='checkbox' ? e.checked : e.value,
                 Math.round(e.getBoundingClientRect().top + scrollY)].join('|'))
```

Field `name`s are often meaningless ("Text7"), and the *label* is only visible in the rendered page. Pair the DOM
list with screenshots: the vertical order of the inputs matches the visual order of the rows.
For `<select>`, list the `options`; the exact option text matters.
Forms inside an `<iframe>` need the query run in that frame's document.

## 3. Verify the mapping before typing real data
The most common error is an off-by-one shift: a row you didn't notice (e.g. an extra "Geburtsname" line) moves
every later value down one field. Before filling a block:
1. Count the visible rows against the inputs in that block.
2. Fill, then take a screenshot (zoom in if needed) and compare each label with its value.
3. If something shifted, set the affected fields again (re-setting a value is harmless).

## 4. Setting values so the page notices
If your browser tool's own fill/select/check commands work on the page, use them. Framework-driven pages
(React, Angular, e-sign widgets) often ignore a plain `el.value = ...` and drop the value on the next render. Then use
the native setter and fire the events the framework listens for:

```js
const setEl=(e,v)=>{e.focus();
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,v);
  e.dispatchEvent(new Event('input',{bubbles:true}));
  e.dispatchEvent(new Event('change',{bubbles:true})); e.blur();};
```
(For a `<textarea>` use `HTMLTextAreaElement.prototype`.)
- `<select>`: set `selectedIndex`, then dispatch `change`.
- Radios/checkboxes: `el.click()` (coordinate clicks miss tiny targets), then read `.checked` back.
- Don't press Enter in a text field, and don't use any "fill and submit" option: Enter submits many forms.
- Fill several fields per step. These pages re-render slowly, and many round trips get fragile.
- Read the values back after filling; some fields reformat or reject input (date pickers, masked IBAN fields).

## 5. Scrolling and screenshots on canvas/widget pages
- `scrollIntoView()` can scroll the *outer* shell and blank the viewer. Use `window.scrollTo(0, y)` with the
  absolute `top` from step 2, then wait about 2 s before a screenshot.
- Screenshot timed out, or came back as a grey blank frame: retry once or twice.
- A taller viewport shows more of the page per screenshot, if your tool lets you resize.
- These pages render lazily: far-away pages may stay empty until you scroll to them.

## 6. Things to leave alone (and report)
- Signature fields ("Zum Signieren klicken", "Sign here", drawn signatures, `echosign_signature`).
- Initials, legal "I agree" acknowledgements the user didn't ask you to give, CAPTCHAs.
- File-upload slots (the user uploads documents themselves).
- Submit / Finish / Send / Save buttons, including the send button of contact or chat forms. Never press them;
  the user decides.

Date and place fields next to a signature are fine to fill with the stored city and today's date. Mention that you
did, because on some forms the date is stamped automatically at signing.

## 7. Yes/no and consent questions
Radios like "other employment?", "photo consent" or "data processing consent" are decisions, not facts. If the
profile has a stored answer, use it. If not, ask the user, store the answer, and never default to "yes" for a
consent. In demo mode the user may tell you to pick arbitrary values.

## 8. Dynamic forms and wizards
Answers can reveal new fields (conditional sections, multi-step wizards). After each batch, run the field discovery
again. Moving to the next step with a plain "Next/Weiter" is fine only when it doesn't submit or save data on the
server. If you're unsure, stop and ask.
