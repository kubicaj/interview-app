import os
import gradio as gr

from src.interview_app import InterviewApp
from src.interview_config import InterviewConfig
# Load all currently open interview positions from the config
POSITIONS = list(InterviewConfig.get_active_instance().all_open_positions.values())

def load_position_detail(position_index):
    """
    Displays detailed information about a selected job position

    Args:
      position_index (int) - Index of the selected position from POSITIONS

    Return:
      (tuple) - Updates UI to show job detail section and populate content
    """
    open_position = POSITIONS[position_index]
    return gr.update(visible=True), open_position.open_position_content, open_position.position_title


def hide_position_detail():
    """
    Hides the job detail section

    Return:
      (tuple) - Updates UI to hide job detail section
    """
    return gr.update(visible=False), "", ""


def set_interview_buttons(disable=True):
    """
    Sets interactivity of all interview buttons

    Args:
      disable (bool) - Whether to disable (True) or enable (False) buttons

    Return:
      (list) - List of button update commands for all positions
    """
    return [gr.update(interactive=(not disable)) for _ in POSITIONS]


def start_interview(position_index: int, cv_content: str):
    """
    Initializes the interview session for a selected position

    Args:
      position_index (int) - Index of the selected position from POSITIONS
      cv_content (str) - Text content extracted from the uploaded CV

    Return:
      (tuple) - Updates UI state, disables other interview buttons, sets chatbot history and app state
    """
    initial_message = (
        f"Hi. You are here because you apply for position {POSITIONS[position_index].position_title}. Can we start please?"
    )
    interview_app = InterviewApp(POSITIONS[position_index].position_identifier, cv_content)
    interview_app.create_graph()
    return (
        gr.update(visible=True),
        POSITIONS[position_index].position_title,
        position_index,
        *set_interview_buttons(disable=True),
        [{"role": "assistant", "content": initial_message}],
        [{"role": "assistant", "content": initial_message}],
        interview_app
    )


def show_confirm_modal():
    """
    Shows the interview end confirmation modal

    Return:
      (gr.update) - Makes the modal visible
    """
    return gr.update(visible=True)


def hide_confirm_modal():
    """
    Hides the interview end confirmation modal

    Return:
      (gr.update) - Hides the modal
    """
    return gr.update(visible=False)


def end_interview_with_summary(interview_app: InterviewApp, history: list[dict]):
    """
    Ends the interview and loads the summary file for display

    Args:
      interview_app (InterviewApp) - Current interview session instance
      history (list[dict]) - Full chat history

    Return:
      (tuple) - UI updates, chat resets, interview buttons enabled, summary display populated

    Raise:
      (FileNotFoundError) - If the summary file does not exist
    """
    interview_app.invoke_user_query("Finish the interview now", history)
    summary_text = ""
    filename = f"summaries{os.path.sep}interview_summary_{interview_app.session_id}.md"
    with open(filename, "r") as file:
        summary_text = file.read()
    return (
        gr.update(visible=False), "", -1,
        *set_interview_buttons(disable=False),
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=True),
        summary_text,
        filename
    )


def chat_function(user_input, history: list[dict], interview_app: InterviewApp):
    """
    Processes user input in the chat and appends response from AI interviewer

    Args:
      user_input (str) - Message from the user
      history (list[dict]) - Chat history
      interview_app (InterviewApp) - Active interview application

    Return:
      (tuple) - Updated chatbot history, state, and clears message input
    """
    try:
        result = interview_app.invoke_user_query(user_input, history)
    except Exception as ex:
        interview_app.logger.exception(ex)
        result = {"role": "assistant", "content": "Unexpected issue happen. Please try to answer again"}
    history = history + [{"role": "user", "content": user_input}] + [result]
    return history, history, ""


def chunk(seq, size):
    """
    Splits a list into chunks of given size

    Args:
      seq (list) - The list to split
      size (int) - Maximum size of each chunk

    Return:
      (generator) - Yields chunked lists
    """
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def handle_cv_upload(file):
    """
    Handles the uploaded CV and parses its content

    Args:
      file (file) - Uploaded PDF file

    Return:
      (tuple) - UI updates to show status and parsed CV text
    """
    if file is None:
        return gr.update(visible=True), gr.update(visible=False), ""
    content_of_cv = InterviewConfig.get_pdf_content(file)
    return gr.update(visible=False), gr.update(
        visible=True), "✅ CV received! You may now browse open positions.", content_of_cv
