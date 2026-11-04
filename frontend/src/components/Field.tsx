import { useId, type InputHTMLAttributes } from 'react';

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hint?: string;
  error?: string;
}

export function Field({ label, hint, error, id, ...props }: FieldProps): JSX.Element {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const descriptionId = `${inputId}-description`;
  return (
    <div className={`field ${error ? 'field-error' : ''}`.trim()}>
      <label htmlFor={inputId}>{label}</label>
      <input
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={hint || error ? descriptionId : undefined}
        {...props}
      />
      {(hint || error) && (
        <p id={descriptionId} className={error ? 'field-message error' : 'field-message'}>
          {error ?? hint}
        </p>
      )}
    </div>
  );
}
