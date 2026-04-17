/**
 * Configuração por ambiente. Escopo atual: staging e prod.
 * Dev fica em localhost via docker-compose — não precisa de stack.
 */

import * as cdk from "aws-cdk-lib";

export interface EnvironmentConfig {
  /** Nome para prefixar stacks e recursos. */
  name: string;
  /** AWS account + region. */
  awsEnv: cdk.Environment;
  /** App Runner: CPU em vCPU units (0.25, 0.5, 1, 2, 4). */
  appRunnerCpu: string;
  /** App Runner: memória em GB (0.5, 1, 2, 3, 4, 6, 8, 10, 12). */
  appRunnerMemory: string;
  /** Max instances para auto-scaling. */
  appRunnerMaxInstances: number;
  /** Domínio do backend. Null = usar URL default gerada pelo App Runner. */
  backendDomain: string | null;
  /** Origem permitida em CORS (URL do frontend). */
  frontendOrigin: string;
  /** Repo GitHub para OIDC. Formato: "owner/repo". */
  githubRepo: string;
  /** Budget alert threshold em USD/mês. */
  monthlyBudgetUsd: number;
}

const STAGING: EnvironmentConfig = {
  name: "staging",
  awsEnv: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || "us-east-1",
  },
  appRunnerCpu: "0.25 vCPU",
  appRunnerMemory: "0.5 GB",
  appRunnerMaxInstances: 2,
  backendDomain: null, // usa xxx.awsapprunner.com
  frontendOrigin: "https://staging.kratos-suno.pages.dev",
  githubRepo: "fbmou/kratos-suno-prompt",
  monthlyBudgetUsd: 50,
};

const PROD: EnvironmentConfig = {
  name: "prod",
  awsEnv: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || "us-east-1",
  },
  appRunnerCpu: "1 vCPU",
  appRunnerMemory: "2 GB",
  appRunnerMaxInstances: 10,
  backendDomain: "api.kratos-suno.felipemoulin.com",
  frontendOrigin: "https://kratos-suno.felipemoulin.com",
  githubRepo: "fbmou/kratos-suno-prompt",
  monthlyBudgetUsd: 300,
};

export function getConfig(envName: string): EnvironmentConfig {
  switch (envName) {
    case "staging":
      return STAGING;
    case "prod":
      return PROD;
    default:
      throw new Error(
        `Unknown environment: ${envName}. Use 'staging' or 'prod' via --context env=X`,
      );
  }
}
