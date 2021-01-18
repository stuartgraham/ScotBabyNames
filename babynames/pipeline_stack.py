from aws_cdk import core
from aws_cdk import aws_codepipeline as codepipeline
from aws_cdk import aws_codepipeline_actions as cpactions
from aws_cdk import pipelines

from .babynames_stack import ApplicationStage

class PipelineStack(core.Stack):
    def __init__(self, scope: core.Construct, id:str, **kwargs):
        super().__init__(scope, id, **kwargs)

        source_artifact = codepipeline.Artifact()
        cloud_assembly_artifact = codepipeline.Artifact()

        pipeline = pipelines.CdkPipeline(self, 'Pipeline', 
            cloud_assembly_artifact=cloud_assembly_artifact,
            pipeline_name='BabyNamesPipeline',
            source_action=cpactions.GitHubSourceAction(
                action_name='GitHub',
                output=source_artifact,
                oauth_token=core.SecretValue.secrets_manager('github-token'),
                owner='stuartgraham',
                repo='ScotBabyNames',
                branch='main',
                trigger=cpactions.GitHubTrigger.POLL),
            
            synth_action=pipelines.SimpleSynthAction(
                source_artifact=source_artifact,
                cloud_assembly_artifact=cloud_assembly_artifact,
                install_commands=['npm install -g aws-cdk && pip install -r requirements.txt'],
                build_commands=[''],
                synth_command='cdk synth'
            ))

        dev_stage = pipeline.add_application_stage(ApplicationStage(self, 'Development', cdk_env_='Development', env={
            'account': '811799881965',
            'region': 'eu-west-1'
        }))

        dev_stage.add_manual_approval_action(
            action_name='Promotion'
        )
        
        pipeline.add_application_stage(ApplicationStage(self, 'Production', cdk_env_='Production', env={
            'account': '756754323790',
            'region': 'eu-west-1'
        }))