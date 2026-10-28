export {};

declare global {
  interface Window {
    feiDesktop?: {
      platform: "windows";
      careerBrowser: {
        open(input: { url: string; applicationId?: string }): Promise<{ ok: boolean }>;
        close(): Promise<{ ok: boolean }>;
        back(): Promise<{ ok: boolean }>;
        forward(): Promise<{ ok: boolean }>;
        reload(): Promise<{ ok: boolean }>;
        reviewApplication(input: { applicationId: string }): Promise<{
          ok: boolean;
          reviewId?: string;
          observedStatus?: string;
          confidence?: number;
          requiresUserAction: boolean;
          blocked: boolean;
        }>;
        getState(): Promise<{ open: boolean; url?: string; title?: string; canGoBack: boolean; canGoForward: boolean; applicationId?: string }>;
      };
    };
  }
}
