import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useMemo,
} from 'react';
import type { ReactNode } from 'react';
import { ProvidersAPI } from '../services/api';

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

export function AnalyzeOptionsProvider({ children }: { children: ReactNode }) {
  const [options, setOptions] = useState<AnalyzeOptions>({ ...DEFAULT_OPTIONS });

  useEffect(() => {
    let cancelled = false;

    void ProvidersAPI.getDefaults()
      .then((defaultsPayload) => {
        if (cancelled) return;
        const descriptionDefaults = defaultsPayload.description;
        if (descriptionDefaults?.provider) {
          setOptions((prev) => ({
            ...prev,
            providerId: descriptionDefaults.provider,
            providerModel: descriptionDefaults.model ?? null,
          }));
        }
      })
      .catch(() => {
        /* keep local defaults — Analyze tab can still render */
      });

    return () => {
      cancelled = true;
    };
  }, []);

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

// eslint-disable-next-line react-refresh/only-export-components -- hook lives with provider
export function useAnalyzeOptions() {
  const context = useContext(AnalyzeOptionsContext);
  if (!context) throw new Error('useAnalyzeOptions must be used within AnalyzeOptionsProvider');
  return context;
}
