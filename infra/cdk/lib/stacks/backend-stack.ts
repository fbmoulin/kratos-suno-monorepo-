/**
 * BackendStack — App Runner servindo o FastAPI de Kratos Suno.
 *
 * Componentes:
 *  - ECR repo (imagens Docker do backend)
 *  - Secrets Manager: ANTHROPIC_API_KEY, SHARED_SECRET, DATABASE_URL (Neon), SPOTIFY_CLIENT_ID
 *  - App Runner service (auto-scaling, HTTPS automático)
 *  - IAM instance role para App Runner ler secrets
 *  - CloudWatch alarms: taxa de 5xx + latência p99
 *  - SNS topic para alertas (email de Felipe)
 *  - AWS Budget com alert em 80% do threshold
 *
 * Decisões:
 *  - Sem VPC — App Runner em public-network. Neon é serverless com SSL,
 *    não exige VPC peering. Economiza ~$32/mês de NAT Gateway.
 *  - Sem RDS — Neon gerencia. CDK só stores connection string no Secrets Manager.
 *  - Image source: ECR com tag "latest" + auto-deploy on push. Alternativa:
 *    source: code (GitHub connection). Optamos por ECR para desacoplar CI do App Runner.
 */

import * as cdk from "aws-cdk-lib";
import * as apprunner from "aws-cdk-lib/aws-apprunner";
import * as budgets from "aws-cdk-lib/aws-budgets";
import * as cloudwatch from "aws-cdk-lib/aws-cloudwatch";
import * as cwActions from "aws-cdk-lib/aws-cloudwatch-actions";
import * as ecr from "aws-cdk-lib/aws-ecr";
import * as iam from "aws-cdk-lib/aws-iam";
import * as logs from "aws-cdk-lib/aws-logs";
import * as sns from "aws-cdk-lib/aws-sns";
import * as subscriptions from "aws-cdk-lib/aws-sns-subscriptions";
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";
import { Construct } from "constructs";

import type { EnvironmentConfig } from "../config/environments";

export interface BackendStackProps extends cdk.StackProps {
  config: EnvironmentConfig;
  alertEmail: string;
}

export class BackendStack extends cdk.Stack {
  public readonly serviceArn: string;
  public readonly serviceUrl: string;
  public readonly ecrRepositoryArn: string;

  constructor(scope: Construct, id: string, props: BackendStackProps) {
    super(scope, id, props);

    const { config, alertEmail } = props;

    // -------------------------------------------------------------------
    // 1. ECR repo
    // -------------------------------------------------------------------
    const repo = new ecr.Repository(this, "BackendRepo", {
      repositoryName: `kratos-suno-backend-${config.name}`,
      imageScanOnPush: true,
      lifecycleRules: [
        {
          description: "Keep only 10 most recent images",
          maxImageCount: 10,
        },
      ],
      removalPolicy:
        config.name === "prod" ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY,
    });
    this.ecrRepositoryArn = repo.repositoryArn;

    // -------------------------------------------------------------------
    // 2. Secrets
    //    Criamos os segredos vazios via CDK — o valor é preenchido
    //    manualmente pelo usuário via AWS Console ou CLI (aws secretsmanager
    //    put-secret-value). Isso evita vazar segredos no state do CDK.
    // -------------------------------------------------------------------
    const anthropicKey = new secretsmanager.Secret(this, "AnthropicApiKey", {
      secretName: `kratos-suno/${config.name}/anthropic-api-key`,
      description: "Anthropic API key — preencher manualmente após deploy",
    });

    const sharedSecret = new secretsmanager.Secret(this, "SharedSecret", {
      secretName: `kratos-suno/${config.name}/shared-secret`,
      description: "X-Kratos-Key shared secret (Stage 1 auth). Gerar com openssl rand -hex 24",
      generateSecretString: {
        passwordLength: 48,
        excludePunctuation: true,
      },
    });

    const databaseUrl = new secretsmanager.Secret(this, "DatabaseUrl", {
      secretName: `kratos-suno/${config.name}/database-url`,
      description: "Neon Postgres connection string — formato postgresql+asyncpg://...",
    });

    const spotifyClientId = new secretsmanager.Secret(this, "SpotifyClientId", {
      secretName: `kratos-suno/${config.name}/spotify-client-id`,
      description: "Spotify Client ID (opcional — deixar vazio desabilita integração)",
    });

    // -------------------------------------------------------------------
    // 3. IAM roles para App Runner
    // -------------------------------------------------------------------
    // Access role: App Runner puxa imagens do ECR
    const accessRole = new iam.Role(this, "AppRunnerAccessRole", {
      assumedBy: new iam.ServicePrincipal("build.apprunner.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AWSAppRunnerServicePolicyForECRAccess",
        ),
      ],
    });

    // Instance role: o container em si (para ler secrets em runtime)
    const instanceRole = new iam.Role(this, "AppRunnerInstanceRole", {
      assumedBy: new iam.ServicePrincipal("tasks.apprunner.amazonaws.com"),
    });
    // Least-privilege: só leitura dos 4 segredos especificados
    [anthropicKey, sharedSecret, databaseUrl, spotifyClientId].forEach((s) =>
      s.grantRead(instanceRole),
    );

    // -------------------------------------------------------------------
    // 3b. CloudWatch LogGroup — ownership + retention
    //    App Runner auto-creates /aws/apprunner/<service>/... com retention
    //    infinita por padrão. Declarar o LogGroup via CDK com o mesmo nome
    //    antecipa a criação e aplica retention policy (30d staging, 90d prod).
    // -------------------------------------------------------------------
    const logGroup = new logs.LogGroup(this, "BackendLogGroup", {
      logGroupName: `/aws/apprunner/kratos-suno-backend-${config.name}`,
      retention:
        config.name === "prod"
          ? logs.RetentionDays.THREE_MONTHS
          : logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });
    // Referência para evitar unused-variable lint; App Runner consumirá implicitamente.
    void logGroup;

    // -------------------------------------------------------------------
    // 4. App Runner service
    // -------------------------------------------------------------------
    const service = new apprunner.CfnService(this, "BackendService", {
      serviceName: `kratos-suno-backend-${config.name}`,
      sourceConfiguration: {
        authenticationConfiguration: {
          accessRoleArn: accessRole.roleArn,
        },
        autoDeploymentsEnabled: true, // auto-deploy quando push em :latest
        imageRepository: {
          imageIdentifier: `${repo.repositoryUri}:latest`,
          imageRepositoryType: "ECR",
          imageConfiguration: {
            port: "8000",
            runtimeEnvironmentVariables: [
              { name: "DEBUG", value: "false" },
              { name: "LOG_FORMAT", value: "json" },
              { name: "AUTH_PROVIDER", value: "shared" },
              { name: "FRONTEND_ORIGIN", value: config.frontendOrigin },
              { name: "ACTIVE_PROMPT_VERSION", value: "v2_stricter" },
              { name: "DNA_EXTRACTOR_MODEL", value: "claude-haiku-4-5-20251001" },
              { name: "AUDIO_DNA_MODEL", value: "claude-sonnet-4-6" },
              {
                name: "SPOTIFY_REDIRECT_URI",
                value: config.backendDomain
                  ? `https://${config.backendDomain}/api/v1/auth/spotify/callback`
                  : "", // Será preenchido após primeiro deploy conhecer a URL
              },
            ],
            runtimeEnvironmentSecrets: [
              { name: "ANTHROPIC_API_KEY", value: anthropicKey.secretArn },
              { name: "SHARED_SECRET", value: sharedSecret.secretArn },
              { name: "DATABASE_URL", value: databaseUrl.secretArn },
              { name: "SPOTIFY_CLIENT_ID", value: spotifyClientId.secretArn },
            ],
          },
        },
      },
      instanceConfiguration: {
        cpu: config.appRunnerCpu,
        memory: config.appRunnerMemory,
        instanceRoleArn: instanceRole.roleArn,
      },
      healthCheckConfiguration: {
        protocol: "HTTP",
        path: "/health",
        interval: 10,
        timeout: 5,
        healthyThreshold: 1,
        unhealthyThreshold: 5,
      },
      autoScalingConfigurationArn: undefined, // usa default (max 25, min 1, concurrency 100)
    });

    this.serviceArn = service.attrServiceArn;
    this.serviceUrl = `https://${service.attrServiceUrl}`;

    // -------------------------------------------------------------------
    // 5. SNS + CloudWatch alarms
    // -------------------------------------------------------------------
    const alertTopic = new sns.Topic(this, "AlertsTopic", {
      topicName: `kratos-suno-alerts-${config.name}`,
      displayName: "Kratos Suno Alerts",
    });
    alertTopic.addSubscription(new subscriptions.EmailSubscription(alertEmail));

    // Alarm: 5xx rate alto (>5 em 5min)
    const alarm5xx = new cloudwatch.Alarm(this, "High5xxRate", {
      alarmName: `kratos-suno-${config.name}-high-5xx`,
      alarmDescription: "Backend 5xx error rate excedeu threshold",
      metric: new cloudwatch.Metric({
        namespace: "AWS/AppRunner",
        metricName: "5xxStatusResponses",
        dimensionsMap: { ServiceName: service.serviceName! },
        statistic: "Sum",
        period: cdk.Duration.minutes(5),
      }),
      threshold: 5,
      evaluationPeriods: 2,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });
    alarm5xx.addAlarmAction(new cwActions.SnsAction(alertTopic));

    // Alarm: latência p99 > 3s (backend com librosa é naturalmente lento)
    const alarmLatency = new cloudwatch.Alarm(this, "HighLatency", {
      alarmName: `kratos-suno-${config.name}-high-latency`,
      alarmDescription: "Latência p99 excedeu 3 segundos",
      metric: new cloudwatch.Metric({
        namespace: "AWS/AppRunner",
        metricName: "RequestLatency",
        dimensionsMap: { ServiceName: service.serviceName! },
        statistic: "p99",
        period: cdk.Duration.minutes(5),
      }),
      threshold: 3000, // ms
      evaluationPeriods: 3,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });
    alarmLatency.addAlarmAction(new cwActions.SnsAction(alertTopic));

    // Alarm: saúde do serviço
    const alarmHealth = new cloudwatch.Alarm(this, "UnhealthyInstances", {
      alarmName: `kratos-suno-${config.name}-unhealthy`,
      alarmDescription: "Instâncias unhealthy detectadas",
      metric: new cloudwatch.Metric({
        namespace: "AWS/AppRunner",
        metricName: "ActiveInstances",
        dimensionsMap: { ServiceName: service.serviceName! },
        statistic: "Minimum",
        period: cdk.Duration.minutes(5),
      }),
      threshold: 1,
      evaluationPeriods: 3,
      comparisonOperator: cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.BREACHING,
    });
    alarmHealth.addAlarmAction(new cwActions.SnsAction(alertTopic));

    // -------------------------------------------------------------------
    // 6. AWS Budget — alerta antes da dor
    // -------------------------------------------------------------------
    new budgets.CfnBudget(this, "MonthlyBudget", {
      budget: {
        budgetName: `kratos-suno-${config.name}-monthly`,
        budgetType: "COST",
        timeUnit: "MONTHLY",
        budgetLimit: {
          amount: config.monthlyBudgetUsd,
          unit: "USD",
        },
        costFilters: {
          TagKeyValue: [`user:project$kratos-suno-prompt`],
        },
      },
      notificationsWithSubscribers: [
        {
          notification: {
            notificationType: "ACTUAL",
            comparisonOperator: "GREATER_THAN",
            threshold: 80,
            thresholdType: "PERCENTAGE",
          },
          subscribers: [{ subscriptionType: "EMAIL", address: alertEmail }],
        },
        {
          notification: {
            notificationType: "FORECASTED",
            comparisonOperator: "GREATER_THAN",
            threshold: 100,
            thresholdType: "PERCENTAGE",
          },
          subscribers: [{ subscriptionType: "EMAIL", address: alertEmail }],
        },
      ],
    });

    // -------------------------------------------------------------------
    // 7. Outputs — úteis pro GitHub Actions e troubleshooting
    // -------------------------------------------------------------------
    new cdk.CfnOutput(this, "ServiceUrl", {
      value: this.serviceUrl,
      description: "URL pública do backend App Runner",
      exportName: `kratos-suno-${config.name}-service-url`,
    });
    new cdk.CfnOutput(this, "EcrRepoUri", {
      value: repo.repositoryUri,
      description: "URI do repositório ECR — usar em docker push",
      exportName: `kratos-suno-${config.name}-ecr-uri`,
    });
    new cdk.CfnOutput(this, "ServiceArn", {
      value: this.serviceArn,
      description: "ARN do App Runner service (para aws apprunner start-deployment)",
      exportName: `kratos-suno-${config.name}-service-arn`,
    });
    new cdk.CfnOutput(this, "AlertsTopicArn", {
      value: alertTopic.topicArn,
      description: "SNS topic para alertas",
    });
  }
}
