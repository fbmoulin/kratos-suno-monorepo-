/**
 * Smoke test: garante que a stack sintetiza sem erros e contém
 * os recursos críticos esperados.
 */

import * as cdk from "aws-cdk-lib";
import { Template } from "aws-cdk-lib/assertions";

import { getConfig } from "../lib/config/environments";
import { BackendStack } from "../lib/stacks/backend-stack";

describe("BackendStack", () => {
  // CDK Stack synthesis precisa de account/region definidos para Template.fromStack.
  // Usamos valores dummy aqui para não depender de CDK_DEFAULT_* do ambiente de CI.
  const originalEnv = process.env;
  beforeAll(() => {
    process.env = {
      ...originalEnv,
      CDK_DEFAULT_ACCOUNT: "123456789012",
      CDK_DEFAULT_REGION: "us-east-1",
    };
  });
  afterAll(() => {
    process.env = originalEnv;
  });

  function buildStack(envName: "staging" | "prod" = "staging") {
    const app = new cdk.App();
    return new BackendStack(app, `TestBackend-${envName}`, {
      config: getConfig(envName),
      alertEmail: "test@example.com",
    });
  }

  test("synthesizes without errors and contains expected resources", () => {
    const stack = buildStack();
    const template = Template.fromStack(stack);

    // ECR repo criado
    template.resourceCountIs("AWS::ECR::Repository", 1);

    // 4 secrets obrigatórios
    template.resourceCountIs("AWS::SecretsManager::Secret", 4);

    // 1 App Runner service
    template.resourceCountIs("AWS::AppRunner::Service", 1);

    // 3 alarms (5xx + latência + health)
    template.resourceCountIs("AWS::CloudWatch::Alarm", 3);

    // 1 SNS topic + 1 budget
    template.resourceCountIs("AWS::SNS::Topic", 1);
    template.resourceCountIs("AWS::Budgets::Budget", 1);

    // Service tem health check configurado
    template.hasResourceProperties("AWS::AppRunner::Service", {
      HealthCheckConfiguration: {
        Protocol: "HTTP",
        Path: "/health",
      },
    });
  });

  test("LogGroup has retention policy (30d staging)", () => {
    const stack = buildStack("staging");
    const template = Template.fromStack(stack);
    template.hasResourceProperties("AWS::Logs::LogGroup", {
      RetentionInDays: 30, // ONE_MONTH para staging
      LogGroupName: "/aws/apprunner/kratos-suno-backend-staging",
    });
  });

  test("LogGroup has retention policy (90d prod)", () => {
    const stack = buildStack("prod");
    const template = Template.fromStack(stack);
    template.hasResourceProperties("AWS::Logs::LogGroup", {
      RetentionInDays: 90, // THREE_MONTHS para prod
      LogGroupName: "/aws/apprunner/kratos-suno-backend-prod",
    });
  });
});
