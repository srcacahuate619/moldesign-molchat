import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, it, expect } from "vitest";
import MessageText from "./MessageText";

afterEach(cleanup);

it("renders common Markdown without interpreting HTML", () => {
  render(<MessageText text={'### Propiedades\n* **Peso:** 180.16\n`CC1`\n<script>alert(1)</script>'} />);
  expect(screen.getByText('Propiedades')).toHaveClass('message-heading');
  expect(screen.getByText('Peso:').tagName).toBe('STRONG');
  expect(screen.getByText('CC1').tagName).toBe('CODE');
  expect(screen.getByText('<script>alert(1)</script>')).toBeInTheDocument();
});

it("renders model Markdown tables as accessible tables with escaped pipes", () => {
  render(<MessageText text={'Comparación\n\n| Propiedad | PubChem | RDKit |\n| :--- | ---: | --- |\n| **LogP** | 1.2 | 1.31 |\n| Nota | A\\|B | correcto |'} />);
  expect(screen.getByRole('table')).toBeInTheDocument();
  expect(screen.getByRole('columnheader', { name: 'PubChem' })).toBeInTheDocument();
  expect(screen.getByRole('cell', { name: '1.31' })).toBeInTheDocument();
  expect(screen.getByRole('cell', { name: 'A|B' })).toBeInTheDocument();
});
