"use client";

import type { ModelInputSchema, ParamSchema, ParamValue } from "@/lib/generation-params";
import { paramLabel } from "@/lib/generation-params";

interface SchemaParamsFormProps {
  schema: ModelInputSchema;
  values: Record<string, ParamValue>;
  errors: Record<string, string>;
  onChange: (name: string, value: ParamValue) => void;
  /** Prefix for input ids so multiple forms can coexist on a page. */
  idPrefix?: string;
}

const inputClasses =
  "w-full px-3 py-2 rounded-xl bg-[#0F1117] border border-[#262A35] text-sm text-[#E8EAF0] " +
  "placeholder:text-[#6B7280] focus:outline-none focus:ring-2 focus:ring-[#7C5CFF] " +
  "disabled:opacity-50";

function renderControl(
  name: string,
  property: ParamSchema,
  value: ParamValue,
  onChange: (name: string, value: ParamValue) => void,
  inputId: string,
  describedBy: string | undefined,
  hasError: boolean
) {
  const shared = {
    id: inputId,
    name,
    "aria-invalid": hasError || undefined,
    "aria-describedby": describedBy,
    className: inputClasses,
  };

  if (property.enum && property.enum.length > 0) {
    const current = value === undefined || value === null ? "" : String(value);
    return (
      <select
        {...shared}
        value={current}
        onChange={(event) => onChange(name, event.target.value)}
      >
        {current === "" && <option value="">Select…</option>}
        {property.enum.map((option) => (
          <option key={String(option)} value={String(option)}>
            {String(option)}
          </option>
        ))}
      </select>
    );
  }

  switch (property.type) {
    case "boolean":
      return (
        <label className="flex items-center gap-2 text-sm text-[#C7CBD6]">
          <input
            id={inputId}
            name={name}
            type="checkbox"
            checked={value === true}
            onChange={(event) => onChange(name, event.target.checked)}
            className="h-4 w-4 rounded border-[#262A35] bg-[#0F1117] text-[#7C5CFF] focus:ring-[#7C5CFF]"
          />
          <span>Enabled</span>
        </label>
      );
    case "integer":
    case "number":
      return (
        <input
          {...shared}
          type="number"
          inputMode={property.type === "integer" ? "numeric" : "decimal"}
          step={property.type === "integer" ? 1 : "any"}
          min={property.minimum}
          max={property.maximum}
          value={value === undefined || value === null ? "" : String(value)}
          onChange={(event) => onChange(name, event.target.value)}
        />
      );
    default:
      return (
        <input
          {...shared}
          type="text"
          value={value === undefined || value === null ? "" : String(value)}
          onChange={(event) => onChange(name, event.target.value)}
        />
      );
  }
}

/** Renders a generation parameter form from a model's JSON Schema. */
export function SchemaParamsForm({
  schema,
  values,
  errors,
  onChange,
  idPrefix = "param",
}: SchemaParamsFormProps) {
  const properties = Object.entries(schema.properties ?? {});

  if (properties.length === 0) {
    return (
      <p className="text-xs text-[#9AA1B2]">
        This model has no adjustable parameters. Defaults will be used.
      </p>
    );
  }

  return (
    <div className="space-y-4" data-testid="schema-params-form">
      {properties.map(([name, property]) => {
        const inputId = `${idPrefix}-${name}`;
        const errorId = `${inputId}-error`;
        const descriptionId = `${inputId}-description`;
        const error = errors[name];
        const describedBy = [property.description ? descriptionId : null, error ? errorId : null]
          .filter(Boolean)
          .join(" ");

        return (
          <div key={name} className="space-y-1.5">
            <label htmlFor={inputId} className="block text-xs font-medium text-[#C7CBD6]">
              {paramLabel(name, property)}
              {schema.required?.includes(name) && (
                <span className="text-[#FF6B6B] ml-0.5" aria-hidden="true">
                  *
                </span>
              )}
            </label>

            {renderControl(name, property, values[name], onChange, inputId, describedBy || undefined, Boolean(error))}

            {property.description && (
              <p id={descriptionId} className="text-[11px] text-[#6B7280]">
                {property.description}
              </p>
            )}
            {error && (
              <p id={errorId} role="alert" className="text-[11px] text-red-400">
                {error}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
