/**
 * Smoke test: garante que a stack sintetiza sem erros e contém
 * os recursos críticos esperados.
 */

import * as cdk from "aws-cdk-lib";
import { Template } from "aws-cdk-lib/assertions";

import { getConfig } from "../lib/config/environments";
import { BackendStack } from "../lib/stacks/backend-stack";

describe("BackendStack", () => {
  test("synthesizes without errors and contains expected resources", () => {
    const app = new cdk.App();
    const stack = new BackendStack(app, "TestBackend", {
      config: getConfig("staging"),
      alertEmail: "test@example.com",
    });
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
});
