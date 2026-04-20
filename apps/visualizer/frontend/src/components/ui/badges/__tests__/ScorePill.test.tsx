import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ScorePill } from '../ScorePill'

describe('ScorePill', () => {
  it('renders label and formatted score', () => {
    render(<ScorePill score={7.5} label="Identity" />)
    const pill = screen.getByLabelText('Identity score 7.5')
    expect(pill).toBeInTheDocument()
    expect(pill).toHaveTextContent('Identity')
    expect(pill).toHaveTextContent('7.5')
  })

  it('renders integer score without decimal', () => {
    render(<ScorePill score={8} label="Street" />)
    expect(screen.getByLabelText('Street score 8')).toHaveTextContent('8')
  })

  it('uses green class for high scores (>=7)', () => {
    const { container } = render(<ScorePill score={7.2} />)
    expect(container.firstChild?.textContent).toContain('7.2')
    expect((container.firstChild as HTMLElement).className).toContain('text-green-700')
  })

  it('uses yellow class for mid scores (5–6.x)', () => {
    const { container } = render(<ScorePill score={5.5} />)
    expect((container.firstChild as HTMLElement).className).toContain('text-yellow-700')
  })

  it('uses red class for low scores (<5)', () => {
    const { container } = render(<ScorePill score={3.1} />)
    expect((container.firstChild as HTMLElement).className).toContain('text-red-700')
  })

  it('renders muted em-dash when score is null', () => {
    render(<ScorePill score={null} label="Identity" />)
    const pill = screen.getByLabelText('Identity score —')
    expect(pill).toHaveTextContent('—')
    expect(pill.className).toContain('text-text-secondary')
  })

  it('renders muted em-dash when score is undefined', () => {
    render(<ScorePill score={undefined} />)
    expect(screen.getByLabelText('Score —')).toHaveTextContent('—')
  })
})
