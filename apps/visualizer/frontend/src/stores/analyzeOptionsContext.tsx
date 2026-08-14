import { createContext, useContext, useLayoutEffect, useState, useCallback, useMemo, Suspense } from 'react';
import type { ReactNode } from 'react';
import { ProvidersAPI } from '../services/api';
import { useQuery } from '../data';

interface AnalyzeOptions {
  providerId: string | null;
  providerModel: string | null;
  maxWorkers: number;
  skipUndescribed: boolean;
}

const DEFAULT_OPTIONS: AnalyzeOptions = {
  providerId: null,
  providerModel: null,
  maxWorkers: 4,
  skipUndescribed: true,
};

interface AnalyzeOptionsContextValue {
  options: AnalyzeOptions;
  updateOption: <K extends keyof AnalyzeOptions>(key: K, value: AnalyzeOptions[K]) => void;
  resetOptions: () => void;
}

const AnalyzeOptionsContext = createContext<AnalyzeOptionsContextValue | null>(null);

function AnalyzeOptionsProviderImpl({ children }: { children: ReactNode }) {
  const defaultsPayload = useQuery(['providers.defaults'] as const, () => ProvidersAPI.getDefaults());
  const [options, setOptions] = useState<AnalyzeOptions>({ ...DEFAULT_OPTIONS });

  useLayoutEffect(() => {
    const visionComparison = defaultsPayload.vision_comparison;
    if (visionComparison?.provider) {
      setOptions((prev) => ({
        ...prev,
        providerId: visionComparison.provider,
        providerModel: visionComparison.model ?? null,
      }));
    }
  }, [defaultsPayload]);

  const updateOption = useCallback(<K extends keyof AnalyzeOptions>(key: K, value: AnalyzeOptions[K]) => {
    setOptions((prev) => ({ ...prev, [key]: value }));
  }, []);

  const resetOptions = useCallback(() => {
    setOptions((prev) => ({
      ...DEFAULT_OPTIONS,
      providerId: prev.providerId,
      providerModel: prev.providerModel,
      maxWorkers: prev.maxWorkers,
      skipUndescribed: true,
    }));
  }, []);

  const value = useMemo(() => ({
    options,
    updateOption,
    resetOptions,
  }), [options, updateOption, resetOptions]);

  return (
    <AnalyzeOptionsContext.Provider value={value}>
      {children}
    </AnalyzeOptionsContext.Provider>
  );
}

export function AnalyzeOptionsProvider({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={null}>
      <AnalyzeOptionsProviderImpl>{children}</AnalyzeOptionsProviderImpl>
    </Suspense>
  );
}

// eslint-disable-next-line react-refresh/only-export-components -- hook lives with provider
export function useAnalyzeOptions() {
  const context = useContext(AnalyzeOptionsContext);
  if (!context) throw new Error('useAnalyzeOptions must be used within AnalyzeOptionsProvider');
  return context;
}
