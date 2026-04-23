import { createContext, useContext, useLayoutEffect, useState, useCallback, useMemo, Suspense } from 'react';
import type { ReactNode } from 'react';
import { ProvidersAPI } from '../services/api';
import { ADVANCED_WEIGHTS_MUST_SUM } from '../constants/strings';
import { useQuery } from '../data';

interface MatchOptions {
  providerId: string | null;
  providerModel: string | null;
  threshold: number;
  phashWeight: number;
  descWeight: number;
  visionWeight: number;
  maxWorkers: number;
  skipUndescribed: boolean;
}

const DEFAULT_OPTIONS: MatchOptions = {
  providerId: null,
  providerModel: null,
  threshold: 0.7,
  phashWeight: 0,
  descWeight: 0,
  visionWeight: 1,
  maxWorkers: 4,
  skipUndescribed: true,
};

interface MatchOptionsContextValue {
  options: MatchOptions;
  updateOption: <K extends keyof MatchOptions>(key: K, value: MatchOptions[K]) => void;
  resetOptions: () => void;
  weightsError: string | null;
}

const MatchOptionsContext = createContext<MatchOptionsContextValue | null>(null);

function MatchOptionsProviderImpl({ children }: { children: ReactNode }) {
  const defaultsPayload = useQuery(['providers.defaults'] as const, () => ProvidersAPI.getDefaults());
  const [options, setOptions] = useState<MatchOptions>({ ...DEFAULT_OPTIONS });

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

  const updateOption = useCallback(<K extends keyof MatchOptions>(key: K, value: MatchOptions[K]) => {
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

  const weightsError = useMemo(() => {
    const total = options.phashWeight + options.descWeight + options.visionWeight;
    return Math.abs(total - 1.0) >= 0.001 ? ADVANCED_WEIGHTS_MUST_SUM : null;
  }, [options.phashWeight, options.descWeight, options.visionWeight]);

  const value = useMemo(() => ({
    options,
    updateOption,
    resetOptions,
    weightsError,
  }), [options, updateOption, resetOptions, weightsError]);

  return (
    <MatchOptionsContext.Provider value={value}>
      {children}
    </MatchOptionsContext.Provider>
  );
}

export function MatchOptionsProvider({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={null}>
      <MatchOptionsProviderImpl>{children}</MatchOptionsProviderImpl>
    </Suspense>
  );
}

// eslint-disable-next-line react-refresh/only-export-components -- hook lives with provider
export function useMatchOptions() {
  const context = useContext(MatchOptionsContext);
  if (!context) throw new Error('useMatchOptions must be used within MatchOptionsProvider');
  return context;
}
