from typing import List

from langchain_core.messages import SystemMessage, BaseMessage

from src.agent.interview_agent import BaseInterviewAgent
from src.pojo.interview_graph_state import InterviewGraphState
from src.common.llm_factory import LLMFactory


class InterviewAdministrator(BaseInterviewAgent):
    """
    Agent to evaluate the whole interview
    """

    def _create_system_prompt(self, interview_state: InterviewGraphState) -> List[BaseMessage]:
        """
        Create interview evaluator prompt

        Args:
            interview_state - actual state of graph

        Args:
            SystemMessage with prompt
        """
        # if there is nno user query then generate the question
        system_prompt = self.agent_prompt_templates["agent_prompt"].format(**{
            "position_description": self._interview_config.get_position_content(self.chosen_position),
            "candidate_cv": self._interview_config.candidate_cv
        })
        return interview_state.messages + [SystemMessage(content=system_prompt)]

    def agent_callback_implementation(self, interview_state: InterviewGraphState) -> InterviewGraphState:
        """
        Agent callback method. More info see InterviewAgent.agent_callback
        """
        open_ai_llm = LLMFactory.get_chat_open_ai_llm(self.INTERVIEW_ADMINISTRATOR_AGENT_NAME)
        messages = self._create_system_prompt(interview_state)
        response = open_ai_llm.invoke(input=messages)

        # get all communication and message from interview and send it to company
        self._send_result_interview(interview_state, response.content)
        # ADD next agent as END
        new_state = interview_state.create_copy(
            {"role": "assistant",
             "content": "Ok, I created the summary and send it to company"},
            last_agent=self.INTERVIEW_ADMINISTRATOR_AGENT_NAME,
            next_agent=self.INTERVIEW_MANAGER_AGENT_NAME
        )
        return new_state

    def _send_result_interview(self, interview_state: InterviewGraphState, administrator_output: str):
        """
        Send results about interview

        Args:
            interview_state (InterviewGraphState) - graph state
            administrator_output (str) - administrator output with summary
        """
        all_message_history = \
            [f"[{item.message_time}] <{item.subject_role}> : {item.message_content} \n" for one_iter in
             interview_state.iteration for item in one_iter]

        final_output = (
            f"## Interview id \n\n {interview_state.session_id} \n\n## Messages history\n\n {all_message_history} \n\n "
            f"## Summary of interview \n\n  "
            f"{administrator_output}")
        # TODO - send email
        self.logger.info(final_output)
