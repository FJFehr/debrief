# Future plans

Directions for this repo that are not being built now. They are written down so that current work does not make them harder.

## Usable by anyone

Today Debrief is shaped around one reviewer: the documents in `reviewing/`, the ARR form, and a Claude Code login. The aim is a tool that any reviewer can pick up, with their own guidelines, their own venue and their own choice of model.

## A local model

A submission under review is confidential. A model that runs on the reviewer's own machine sends it nowhere, which is better than any hosted setup.

A local model has less context and follows long instructions less reliably. Today the first prompt carries the whole paper, the guidelines, the bias register, the interview process and past reviews, and one long conversation carries the interview. That will not fit.

The work is to isolate the places where a model is used, so that each can be run with a small context and tested on its own:

| Step | What the model does | What has to be decided |
|---|---|---|
| Taking in the document | Reads the paper and the notes | How the paper reaches the model: whole, section by section, or through a compact form such as the claim map from the brief |
| Deciding what to ask | Picks the candidate points, the questions and the bias signals | What each decision needs to see, and what it returns |
| Rewording | Turns an answer into the text of a section; applies a spoken edit | The smallest input that is enough: the answer, the entry, the rules for that section |

What already helps:

- The app, not the model, keeps the state: the stage, the index of points, the record and the assembled draft.
- The app tells the model which step to do next and sends the current index each time.
- Every model call goes through one function, and replies follow a fixed set of fields.

What stands in the way:

- The interview is one long model session that remembers earlier turns.
- The first prompt contains everything at once.
- The reply format relies on the command-line tool's support for structured output.

## Dictation on the machine

The Dictate button uses the browser's speech recognition, which sends audio to the browser maker's service. The aim is speech-to-text that runs on the reviewer's machine, so that nothing spoken about a submission leaves it.

One way: the page records the audio and hands it to the app, which transcribes it with a local speech model. The cost is that words appear when a recording ends, not as they are spoken, and a model has to be downloaded once. Until then, macOS dictation in a text box can run on the machine.

## A Claude skill

Another way to reach people who already use Claude: package the interview as a skill, with the process documents and prompts inside it.

Open questions:

- The page shows the paper beside the interview and links every point to its place. A skill has no page of its own.
- The record is written by the server so that the reviewer's words are stored exactly as sent. Inside a skill something else would have to give that guarantee.
