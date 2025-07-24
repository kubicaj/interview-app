from typing import List, Annotated, Literal

from langchain_core.messages import SystemMessage, BaseMessage
from pydantic import BaseModel

from src.agent.interview_agent import BaseInterviewAgent
from src.pojo.interview_graph_state import InterviewGraphState
from src.custom_types.interview_stage import InterviewStage
from src.common.llm_factory import LLMFactory


class ManagerOutput(BaseModel):
    """
    Structured answer of manager agent
    """
    action_to_take: Annotated[
        Literal["talking_to_technical_lead", "talking_to_candidate", "talking_to_interview_administrator"],
        "With who you are talking right now"]
    stage: Annotated[InterviewStage, "Stage of interview where manager is focus"]
    manager_message: Annotated[str, "Manager message: to user or to technical lead"]


class InterviewManager(BaseInterviewAgent):
    """
    Agent to manage the interview
    """

    def _create_system_prompt(self, interview_state: InterviewGraphState) -> List[BaseMessage]:
        """
        Create interview manager prompt

        Args:
            interview_state - actual state of graph

        Args:
            SystemMessage with prompt
        """
        answer_from_technical_lead = "No answer from technical lead. Feel free to ask"
        if interview_state.last_agent == self.TECH_LEAD_AGENT_NAME and interview_state.generated_question:
            answer_from_technical_lead = interview_state.generated_question
        self.logger.debug("Create interview evaluator prompt...")
        # if there is nno user query then generate the question
        system_prompt = self.agent_prompt_templates["agent_prompt"].format(**{
            "position_description": self._interview_config.get_position_content(self.chosen_position),
            "candidate_cv": self._interview_config.candidate_cv,
            "answer_from_technical_lead": answer_from_technical_lead # last count of messages
        })
        return interview_state.messages + [SystemMessage(content=system_prompt)]

    def agent_callback_implementation(self, interview_state: InterviewGraphState) -> InterviewGraphState:
        """
        Agent callback method. More info see InterviewAgent.agent_callback
        """

        # if there is no last agent, it means that the communication already start and last agent will be this first
        # agent so manager
        if not interview_state.last_agent:
            interview_state.last_agent = self.INTERVIEW_MANAGER_AGENT_NAME

        open_ai_llm = LLMFactory.get_chat_open_ai_llm(self.INTERVIEW_MANAGER_AGENT_NAME)
        llm_with_structured_output = open_ai_llm.with_structured_output(ManagerOutput)
        response: ManagerOutput = llm_with_structured_output.invoke(input=self._create_system_prompt(interview_state))

        # resolve the next agent
        next_agent = "END"
        if response.action_to_take == "talking_to_interview_administrator" and \
                interview_state.last_agent != self.INTERVIEW_ADMINISTRATOR_AGENT_NAME:
            next_agent = self.INTERVIEW_ADMINISTRATOR_AGENT_NAME
        if response.action_to_take == "talking_to_technical_lead":
            next_agent = self.TECH_LEAD_AGENT_NAME
        new_state = interview_state.create_copy(
            {"role": "assistant", "content": response.manager_message},
            last_agent=self.INTERVIEW_MANAGER_AGENT_NAME,
            next_agent=next_agent,
            interview_manager_message=response.manager_message
        )
        # clear this so keep question and formulation of question on manager
        new_state.candidate_query = None
        # process response
        return new_state
