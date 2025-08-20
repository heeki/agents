import asyncio
import os
import yaml
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task, before_kickoff, after_kickoff
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List

@CrewBase
class ExampleCrew():
    agents: List[BaseAgent]
    tasks: List[Task]

    def __init__(self):
        self.llm = LLM(
            model="bedrock/anthropic.claude-3-sonnet-20240229-v1:0"
        )

    @before_kickoff
    def initialize(self, inputs):
        print(f"Initializing crew with inputs: {inputs}")
        return inputs

    @after_kickoff
    def finalize(self, result):
        print(f"Finalizing crew with result: {result}")
        return result

    @agent
    def researcher(self) -> Agent:

        return Agent(
            config=self.agents_config['researcher'],
            llm=self.llm,
            tools=[],
            verbose=True
        )

    @agent
    def reporting_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config['reporting_analyst'],
            llm=self.llm,
            tools=[],
            verbose=True
        )

    @task
    def research_task(self) -> Task:
        return Task(
            config=self.tasks_config['research_task'],
        )

    @task
    def reporting_task(self) -> Task:
        return Task(
        config=self.tasks_config['reporting_task'],
        output_file='output/report.md'
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )

async def main():
    inputs = {
        "topic": "What is VO2 max? What is the best way to improve it?"
    }
    result = await ExampleCrew().crew().kickoff_async(inputs=inputs)
    print(result.raw)

if __name__ == "__main__":
    asyncio.run(main())