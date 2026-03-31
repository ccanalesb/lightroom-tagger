import { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react';
import type { ReactNode } from 'react';
import { ProvidersAPI, SystemAPI } from '../services/api';
import { ADVANCED_WEIGHTS_MUST_SUM } from '../constants/strings';

interface MatchOptions {
  selectedModel: string;
  providerId: string | null;
  providerModel: string | null;
  threshold: number;
  phashWeight: number;
  descWeight: number;
  visionWeight: number;
}

const DEFAULT_OPTIONS: MatchOptions = {
  selectedModel: '',
  providerId: null,
  providerModel: null,
  threshold: 0.7,
  phashWeight: 0,
  descWeight: 0,
  visionWeight: 1,
};

type VisionModelOption = {
  name: string;
  default: boolean;
  provider_id?: string;
};

interface MatchOptionsContextValue {
  options: MatchOptions;
  updateOption: <K extends keyof MatchOptions>(key: K, value: MatchOptions[K]) => void;
  resetOptions: () => void;
  availableModels: VisionModelOption[];
  weightsError: string | null;
}

const MatchOptionsContext = createContext<MatchOptionsContextValue | null>(null);

export function MatchOptionsProvider({ children }: { children: ReactNode }) {
  const [options, setOptions] = useState<MatchOptions>({ ...DEFAULT_OPTIONS });
  const [availableModels, setAvailableModels] = useState<VisionModelOption[]>([]);

  useEffect(() => {
    SystemAPI.visionModels()
      .then((data) => {
        setAvailableModels(data.models);
        const legacyModels = data.models.filter(
          (model) => !model.provider_id || model.provider_id === 'ollama',
        );
        const defaultLegacyModel =
          legacyModels.find((model) => model.default) ?? legacyModels[0];
        if (defaultLegacyModel) {
          setOptions((prev) => ({ ...prev, selectedModel: defaultLegacyModel.name }));
        }
      })
      .catch(console.error);
  }, []);

  useEffect(() => {
    ProvidersAPI.getDefaults()
      .then((defaults) => {
        const visionComparison = defaults.vision_comparison;
        if (!visionComparison?.provider) return;
        setOptions((prev) => ({
          ...prev,
          providerId: visionComparison.provider,
          providerModel: visionComparison.model ?? null,
        }));
      })
      .catch(console.error);
  }, []);

  const updateOption = useCallback(<K extends keyof MatchOptions>(key: K, value: MatchOptions[K]) => {
    setOptions((prev) => ({ ...prev, [key]: value }));
  }, []);

  const resetOptions = useCallback(() => {
    setOptions((prev) => ({
      ...DEFAULT_OPTIONS,
      selectedModel: prev.selectedModel,
      providerId: prev.providerId,
      providerModel: prev.providerModel,
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
    availableModels,
    weightsError,
  }), [options, updateOption, resetOptions, availableModels, weightsError]);

  return (
    <MatchOptionsContext.Provider value={value}>
      {children}
    </MatchOptionsContext.Provider>
  );
}

export function useMatchOptions() {
  const context = useContext(MatchOptionsContext);
  if (!context) throw new Error('useMatchOptions must be used within MatchOptionsProvider');
  return context;
}
