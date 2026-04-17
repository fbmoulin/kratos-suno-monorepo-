/**
 * CicdStack — OIDC provider para GitHub Actions + IAM role least-privilege.
 *
 * GitHub Actions assume esta role via OIDC (trust federado), evitando
 * armazenar IAM access keys em secrets do GitHub. Padrão obrigatório
 * conforme skill aws-deploy.
 *
 * O role tem permissão para:
 *   - Fazer push de imagens no ECR específico
 *   - Iniciar deploy no App Runner específico
 *   - Ler logs do CloudWatch (debug)
 *
 * NÃO pode: criar/deletar recursos, mexer em secrets, criar roles.
 */

import * as cdk from "aws-cdk-lib";
import * as iam from "aws-cdk-lib/aws-iam";
import { Construct } from "constructs";

import type { EnvironmentConfig } from "../config/environments";

export interface CicdStackProps extends cdk.StackProps {
  config: EnvironmentConfig;
  ecrRepositoryArn: string;
  appRunnerServiceArn: string;
}

export class CicdStack extends cdk.Stack {
  public readonly githubActionsRoleArn: string;

  constructor(scope: Construct, id: string, props: CicdStackProps) {
    super(scope, id, props);

    const { config, ecrRepositoryArn, appRunnerServiceArn } = props;

    // -------------------------------------------------------------------
    // 1. OIDC provider — uma só vez por conta AWS
    //    CDK gerencia idempotência: se já existir, importa.
    // -------------------------------------------------------------------
    // ATENÇÃO: se já existir um OIDC provider para token.actions.githubusercontent.com
    // na sua conta (comum se usa GitHub Actions em outros projetos), use:
    //   const provider = iam.OpenIdConnectProvider.fromOpenIdConnectProviderArn(this, "ExistingProvider", "arn:aws:iam::ACCOUNT:oidc-provider/token.actions.githubusercontent.com");
    const provider = new iam.OpenIdConnectProvider(this, "GitHubOidc", {
      url: "https://token.actions.githubusercontent.com",
      clientIds: ["sts.amazonaws.com"],
    });

    // -------------------------------------------------------------------
    // 2. Role assumível apenas pelo repo específico + branches específicas
    // -------------------------------------------------------------------
    const role = new iam.Role(this, "GitHubActionsDeployRole", {
      roleName: `kratos-suno-github-actions-${config.name}`,
      description: `Deploy role para GitHub Actions — repo ${config.githubRepo}`,
      assumedBy: new iam.FederatedPrincipal(
        provider.openIdConnectProviderArn,
        {
          StringEquals: {
            "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          },
          StringLike: {
            // Staging: permite push de qualquer branch
            // Prod: permite apenas main e tags v*
            "token.actions.githubusercontent.com:sub":
              config.name === "prod"
                ? [
                    `repo:${config.githubRepo}:ref:refs/heads/main`,
                    `repo:${config.githubRepo}:ref:refs/tags/v*`,
                  ]
                : `repo:${config.githubRepo}:*`,
          },
        },
        "sts:AssumeRoleWithWebIdentity",
      ),
      maxSessionDuration: cdk.Duration.hours(1),
    });
    this.githubActionsRoleArn = role.roleArn;

    // -------------------------------------------------------------------
    // 3. Permissões — least privilege
    // -------------------------------------------------------------------
    // ECR: login + push/pull no repo específico
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: "EcrLogin",
        effect: iam.Effect.ALLOW,
        actions: ["ecr:GetAuthorizationToken"],
        resources: ["*"], // required for GetAuthorizationToken
      }),
    );
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: "EcrPush",
        effect: iam.Effect.ALLOW,
        actions: [
          "ecr:BatchCheckLayerAvailability",
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:PutImage",
        ],
        resources: [ecrRepositoryArn],
      }),
    );

    // App Runner: start-deployment no serviço específico
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: "AppRunnerDeploy",
        effect: iam.Effect.ALLOW,
        actions: [
          "apprunner:StartDeployment",
          "apprunner:DescribeService",
          "apprunner:ListOperations",
        ],
        resources: [appRunnerServiceArn],
      }),
    );

    // CloudWatch Logs: leitura para debug (não write — App Runner mesmo escreve)
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: "LogsRead",
        effect: iam.Effect.ALLOW,
        actions: [
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
          "logs:GetLogEvents",
          "logs:FilterLogEvents",
        ],
        resources: [
          `arn:aws:logs:${this.region}:${this.account}:log-group:/aws/apprunner/kratos-suno-backend-${config.name}/*`,
        ],
      }),
    );

    // -------------------------------------------------------------------
    // 4. Outputs
    // -------------------------------------------------------------------
    new cdk.CfnOutput(this, "GitHubActionsRoleArn", {
      value: role.roleArn,
      description:
        "ARN para configurar em GitHub repo → Settings → Secrets → AWS_DEPLOY_ROLE_ARN",
      exportName: `kratos-suno-${config.name}-gha-role-arn`,
    });
  }
}
