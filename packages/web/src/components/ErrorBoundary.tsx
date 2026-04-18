import { Component, type ErrorInfo, type ReactNode } from "react";
import {
  Alert,
  AlertDescription,
  AlertIcon,
  AlertTitle,
  Box,
  Button,
  Code,
  VStack,
} from "@chakra-ui/react";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: (error: Error, reset: () => void) => ReactNode;
  onError?: (error: Error, info: ErrorInfo) => void;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Log to console for dev; production hook for e.g. Sentry goes here
    // eslint-disable-next-line no-console
    console.error("[ErrorBoundary]", error, info.componentStack);
    this.props.onError?.(error, info);
  }

  reset = (): void => {
    this.setState({ error: null });
  };

  render(): ReactNode {
    const { error } = this.state;
    const { children, fallback } = this.props;

    if (error === null) {
      return children;
    }

    if (fallback !== undefined) {
      return fallback(error, this.reset);
    }

    return (
      <Box p={8} maxW="2xl" mx="auto" mt={16}>
        <Alert
          status="error"
          variant="subtle"
          flexDirection="column"
          alignItems="flex-start"
          borderRadius="md"
          py={6}
        >
          <Box display="flex" alignItems="center" mb={3}>
            <AlertIcon />
            <AlertTitle ml={2}>Algo deu errado</AlertTitle>
          </Box>
          <AlertDescription as={VStack} alignItems="stretch" spacing={3} w="full">
            <Box>
              Aconteceu um erro inesperado na aplicação. Tente recarregar a
              página ou clique em <strong>Tentar novamente</strong>.
            </Box>
            {import.meta.env.DEV && (
              <Code p={3} borderRadius="md" fontSize="xs" whiteSpace="pre-wrap">
                {error.message}
              </Code>
            )}
            <Button
              onClick={this.reset}
              colorScheme="brand"
              alignSelf="flex-start"
            >
              Tentar novamente
            </Button>
          </AlertDescription>
        </Alert>
      </Box>
    );
  }
}
