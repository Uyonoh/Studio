/**
 * Minimal JSON-Schema support for generation parameter forms.
 *
 * The composer only needs the scalar shapes our model catalog uses today
 * (enum, integer, number, boolean, string). Keeping validation here makes it
 * unit-testable and keeps the React component free of validation logic.
 */

export type ParamValue = string | number | boolean | null | undefined;
export type ParamValues = Record<string, ParamValue>;

export interface ParamSchema {
  type?: string;
  title?: string;
  description?: string;
  enum?: Array<string | number | boolean>;
  minimum?: number;
  maximum?: number;
  minLength?: number;
  maxLength?: number;
  default?: ParamValue;
}

export interface ModelInputSchema {
  type?: string;
  properties?: Record<string, ParamSchema>;
  required?: string[];
  additionalProperties?: boolean;
}

export function isBlank(value: ParamValue): boolean {
  return (
    value === undefined || value === null || (typeof value === "string" && value.trim() === "")
  );
}

function numericValue(value: ParamValue): number | null {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function enumOptions(schema: ParamSchema): Array<string | number | boolean> | null {
  return schema.enum && schema.enum.length > 0 ? schema.enum : null;
}

/** Human-friendly label for a schema property name. */
export function paramLabel(name: string, schema: ParamSchema): string {
  if (schema.title) return schema.title;
  const words = name.replace(/_/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Merge server defaults with per-property `default` values. */
export function defaultParamValues(
  schema: ModelInputSchema,
  defaultParams: Record<string, ParamValue> = {}
): ParamValues {
  const values: ParamValues = { ...defaultParams };
  for (const [name, property] of Object.entries(schema.properties ?? {})) {
    if (values[name] === undefined && property.default !== undefined) {
      values[name] = property.default;
    }
  }
  return values;
}

/**
 * Validate form values against the model schema.
 *
 * Returns a map of property name → error message; an empty object means valid.
 */
export function validateParamValues(
  schema: ModelInputSchema,
  values: ParamValues
): Record<string, string> {
  const errors: Record<string, string> = {};

  for (const [name, property] of Object.entries(schema.properties ?? {})) {
    const value = values[name];
    const required = schema.required?.includes(name) ?? false;

    if (isBlank(value)) {
      if (required) errors[name] = "This field is required";
      continue;
    }

    const options = enumOptions(property);
    if (options) {
      const matches = options.some((option) => String(option) === String(value));
      if (!matches) errors[name] = `Choose one of: ${options.join(", ")}`;
      continue;
    }

    switch (property.type) {
      case "integer": {
        const parsed = numericValue(value);
        if (parsed === null || !Number.isInteger(parsed)) {
          errors[name] = "Enter a whole number";
          break;
        }
        if (property.minimum !== undefined && parsed < property.minimum) {
          errors[name] = `Must be at least ${property.minimum}`;
        } else if (property.maximum !== undefined && parsed > property.maximum) {
          errors[name] = `Must be at most ${property.maximum}`;
        }
        break;
      }
      case "number": {
        const parsed = numericValue(value);
        if (parsed === null) {
          errors[name] = "Enter a number";
          break;
        }
        if (property.minimum !== undefined && parsed < property.minimum) {
          errors[name] = `Must be at least ${property.minimum}`;
        } else if (property.maximum !== undefined && parsed > property.maximum) {
          errors[name] = `Must be at most ${property.maximum}`;
        }
        break;
      }
      case "boolean":
        if (typeof value !== "boolean") {
          errors[name] = "Must be true or false";
        }
        break;
      case "string":
        if (typeof value !== "string") {
          errors[name] = "Enter text";
          break;
        }
        if (property.minLength !== undefined && value.length < property.minLength) {
          errors[name] = `Must be at least ${property.minLength} characters`;
        } else if (property.maxLength !== undefined && value.length > property.maxLength) {
          errors[name] = `Must be at most ${property.maxLength} characters`;
        }
        break;
      default:
        // Unsupported schema shapes are passed through untouched.
        break;
    }
  }

  return errors;
}

/**
 * Coerce form values into the JSON types the API expects.
 *
 * Number inputs hold raw strings while the user is typing, so numeric strings
 * are converted here; enum values are mapped back to their original type.
 * Blank fields are omitted so server defaults apply.
 */
export function normalizeParamValues(
  schema: ModelInputSchema,
  values: ParamValues
): Record<string, unknown> {
  const normalized: Record<string, unknown> = {};

  for (const [name, value] of Object.entries(values)) {
    if (isBlank(value)) continue;

    const property = schema.properties?.[name];
    if (!property) {
      normalized[name] = value;
      continue;
    }

    const options = enumOptions(property);
    if (options) {
      const match = options.find((option) => String(option) === String(value));
      normalized[name] = match !== undefined ? match : value;
      continue;
    }

    if (property.type === "integer" || property.type === "number") {
      const parsed = numericValue(value);
      normalized[name] = parsed === null ? value : parsed;
      continue;
    }

    normalized[name] = value;
  }

  return normalized;
}
