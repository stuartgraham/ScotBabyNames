from os import path
from aws_cdk import core
import aws_cdk.aws_lambda as lmb
import aws_cdk.aws_lambda_event_sources as lmb_events
import aws_cdk.aws_apigatewayv2 as apigw2
import aws_cdk.aws_apigatewayv2_integrations as apigw2int
import aws_cdk.aws_dynamodb as dynamodb
import aws_cdk.aws_sqs as sqs
import aws_cdk.aws_s3 as s3
import aws_cdk.aws_s3_deployment as s3deploy
import aws_cdk.aws_events as events
import aws_cdk.aws_events_targets as targets
import aws_cdk.aws_certificatemanager as acm
import aws_cdk.aws_route53 as route53
import aws_cdk.aws_route53_targets as r53targets
import aws_cdk.aws_ssm as ssm

class ApplicationStage(core.Stage):
    def __init__(self, scope: core.Construct, id: str, cdk_env_='', **kwargs):
        super().__init__(scope, id, **kwargs)
        self.cdk_env_ = cdk_env_

        service = ApplicationStack(self, 'BabyNames', cdk_env_=self.cdk_env_)
        #self.url_output = service.url_output


class ApplicationStack(core.Stack):

    def __init__(self, scope: core.Construct, construct_id: str, cdk_env_='', **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        this_dir = path.dirname(__file__)
        

        # Dynamo DB Tables
        dynamo_names_table = dynamodb.Table(self, 'Names',
            partition_key=dynamodb.Attribute(name='name', type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name='gender', type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST
            )
        dynamo_names_table.add_global_secondary_index(
            partition_key=dynamodb.Attribute(name='gender', type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name='uuid', type=dynamodb.AttributeType.STRING),
            index_name='bn_uuid_sort'
        )


        # Lambda Layers
        lambda_layer_requests = lmb.LayerVersion(self, 'Layer-Requests',
            code = lmb.Code.from_asset(path.join(this_dir, 'lambda/layers/requests.zip')),
            compatible_runtimes = [lmb.Runtime.PYTHON_3_8],
        )
        lambda_layer_simplejson = lmb.LayerVersion(self, 'Layer-SimpleJSON',
            code = lmb.Code.from_asset(path.join(this_dir, 'lambda/layers/simplejson.zip')),
            compatible_runtimes = [lmb.Runtime.PYTHON_3_8],
        )
        lambda_layer_jinja2 = lmb.LayerVersion(self, 'Layer-Jinja2',
            code = lmb.Code.from_asset(path.join(this_dir, 'lambda/layers/jinja2.zip')),
            compatible_runtimes = [lmb.Runtime.PYTHON_3_8],
        )


        ## Lambda - API Handler
        lambda_api_handler = lmb.Function(self, 'API-Handler',
            timeout=core.Duration.seconds(360),
            memory_size=512,
            runtime=lmb.Runtime.PYTHON_3_8,
            handler='api_handler.handler',
            layers=[lambda_layer_simplejson, lambda_layer_jinja2],
            code=lmb.Code.from_asset(path.join(this_dir, 'lambda/api_handler')),
            environment={
                'DYNAMO_DB_NAMES': dynamo_names_table.table_name
            }
        )
        ### Grants
        dynamo_names_table.grant_read_write_data(lambda_api_handler)

        
        # APIGW
        ## Pull domain values from parameter store
        parameter_store_record_name = ssm.StringParameter.value_for_string_parameter(
            self, f'/babynames/{cdk_env_}/record_name')
        parameter_store_domain_name = ssm.StringParameter.value_for_string_parameter(
            self, f'/babynames/{cdk_env_}/domain_name')
        parameter_store_zone_id = ssm.StringParameter.value_for_string_parameter(
            self, f'/babynames/{cdk_env_}/zone_id')

        ## Import R53 Zone
        r53_zone = route53.HostedZone.from_hosted_zone_attributes(self, "R53Zone",
            zone_name=parameter_store_domain_name, hosted_zone_id=parameter_store_zone_id)

        ## ACM Certificate
        acm_certificate = acm.Certificate(self, "BabyNamesCertificate",
            domain_name=parameter_store_record_name,
            validation=acm.CertificateValidation.from_dns(r53_zone)
        )

        ## APIGW Custom Domain
        apigw_baby_names_domain_name = apigw2.DomainName(self, "BabyNamesDomain",
            domain_name=parameter_store_record_name,
            certificate=acm.Certificate.from_certificate_arn(self, "BabyNamesCert", acm_certificate.certificate_arn)
        )
        
        ## Set R53 Records
        r53_alias_target_baby_names_apigw = r53targets.ApiGatewayv2Domain(apigw_baby_names_domain_name)
        route53.ARecord(self, "BabyNamesARecord",
            record_name='babynames',
            zone=r53_zone,
            target=route53.RecordTarget.from_alias(r53_alias_target_baby_names_apigw))

        ## Instantiate APIGW
        apigw_baby_names = apigw2.HttpApi(self, 'BabyNames-APIGW-Http',
        default_domain_mapping=(apigw2.DefaultDomainMappingOptions(domain_name=apigw_baby_names_domain_name)))

        ## APIGW Integrations
        ## Lambda Integrations
        lambda_int_lambda_api_handler = apigw2int.LambdaProxyIntegration(
            handler=lambda_api_handler
        )

        apigw_baby_names.add_routes(
            path='/{name}/{gender}',
            methods=[apigw2.HttpMethod.GET],
            integration=lambda_int_lambda_api_handler
        )

        apigw_baby_names.add_routes(
            path='/{proxy+}',
            methods=[apigw2.HttpMethod.GET],
            integration=lambda_int_lambda_api_handler
        )
