"""
Vesper CLI

Command-line interface for the Vesper framework.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from vesper.compiler import VesperCompiler
from vesper.runtime import VesperRuntime

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="vesper")
def main() -> None:
    """Vesper - Verified execution for LLM-native runtimes."""
    pass


@main.command()
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output", "-o", type=click.Path(path_type=Path), help="Output file path"
)
@click.option(
    "--validate-only", "-v", is_flag=True, help="Only validate, don't compile"
)
def compile(source: Path, output: Path | None, validate_only: bool) -> None:
    """Compile a Vesper specification (.vsp) to Python code."""
    compiler = VesperCompiler()

    try:
        # Parse the specification
        console.print(f"[blue]Parsing[/blue] {source}")
        node = compiler.parse(source)

        # Validate
        console.print(f"[blue]Validating[/blue] {node.node_id}")
        result = compiler.validate(node)

        if result.errors:
            console.print("[red]Validation errors:[/red]")
            for error in result.errors:
                console.print(f"  [red]✗[/red] {error.path}: {error.message}")
            sys.exit(1)

        if result.warnings:
            console.print("[yellow]Warnings:[/yellow]")
            for warning in result.warnings:
                console.print(f"  [yellow]⚠[/yellow] {warning.path}: {warning.message}")

        console.print("[green]✓[/green] Validation passed")

        if validate_only:
            return

        # Compile
        console.print(f"[blue]Compiling[/blue] {node.node_id}")
        code = compiler.compile(node)

        # Write output
        if output is None:
            output = source.with_suffix(".py")
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w") as f:
            f.write(code)

        console.print(f"[green]✓[/green] Generated {output}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--input", "-i", "inputs", multiple=True, help="Input values as key=value"
)
def run(source: Path, inputs: tuple[str, ...]) -> None:
    """Run a Vesper specification with given inputs."""
    runtime = VesperRuntime()

    try:
        # Load the node
        console.print(f"[blue]Loading[/blue] {source}")
        node = runtime.load_node(source)

        console.print(f"[green]✓[/green] Loaded {node.node_id}")
        console.print(f"[dim]Intent: {node.intent}[/dim]")

        # Parse inputs
        input_dict: dict[str, str | int | float | bool] = {}
        for inp in inputs:
            if "=" not in inp:
                console.print(
                    f"[red]Invalid input format:[/red] {inp} (expected key=value)"
                )
                sys.exit(1)
            key, value = inp.split("=", 1)

            # Try to parse as different types
            if value.lower() in ("true", "false"):
                input_dict[key] = value.lower() == "true"
            else:
                try:
                    input_dict[key] = int(value)
                except ValueError:
                    try:
                        input_dict[key] = float(value)
                    except ValueError:
                        input_dict[key] = value

        # Execute
        console.print(f"[blue]Executing[/blue] with inputs: {input_dict}")
        result = runtime.execute_sync(node.node_id, input_dict)

        if result.success:
            console.print(
                Panel(
                    str(result.data),
                    title="[green]Success[/green]",
                    border_style="green",
                )
            )
        else:
            console.print(
                Panel(str(result.error), title="[red]Error[/red]", border_style="red")
            )
            sys.exit(1)

        # Show metrics
        if result.metrics:
            console.print(f"[dim]Duration: {result.metrics.duration_ms:.2f}ms[/dim]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument("source", type=click.Path(exists=True, path_type=Path))
def show(source: Path) -> None:
    """Display information about a Vesper specification."""
    compiler = VesperCompiler()

    try:
        node = compiler.parse(source)

        # Show node information
        console.print(
            Panel(
                f"[bold]{node.node_id}[/bold]\n\n"
                f"[dim]Type:[/dim] {node.type.value}\n"
                f"[dim]Intent:[/dim] {node.intent}",
                title="Node Information",
            )
        )

        # Show inputs
        if node.inputs:
            table = Table(title="Inputs")
            table.add_column("Name", style="cyan")
            table.add_column("Type", style="green")
            table.add_column("Required", style="yellow")
            table.add_column("Description")

            for name, spec in node.inputs.items():
                if isinstance(spec, dict):
                    type_str = spec.get("type", "unknown")
                    required = spec.get("required", True)
                    desc = spec.get("description", "")
                else:
                    type_str = spec.type
                    required = spec.required
                    desc = spec.description or ""

                table.add_row(name, type_str, "✓" if required else "", desc)

            console.print(table)

        # Show contracts
        if node.contracts.preconditions or node.contracts.postconditions:
            console.print("\n[bold]Contracts[/bold]")

            if node.contracts.preconditions:
                console.print("[dim]Preconditions:[/dim]")
                for cond in node.contracts.preconditions:
                    console.print(f"  • {cond}")

            if node.contracts.postconditions:
                console.print("[dim]Postconditions:[/dim]")
                for cond in node.contracts.postconditions:
                    console.print(f"  • {cond}")

        # Show flow
        if node.flow:
            console.print("\n[bold]Execution Flow[/bold]")
            for i, step in enumerate(node.flow, 1):
                console.print(f"  {i}. [cyan]{step.step}[/cyan] ({step.operation})")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument("source", type=click.Path(exists=True, path_type=Path))
def codegen(source: Path) -> None:
    """Show the generated Python code without writing to file."""
    compiler = VesperCompiler()

    try:
        node = compiler.parse(source)
        result = compiler.validate(node)

        if not result.valid:
            console.print("[red]Validation failed:[/red]")
            for error in result.errors:
                console.print(f"  [red]✗[/red] {error.path}: {error.message}")
            sys.exit(1)

        code = compiler.compile(node)

        syntax = Syntax(code, "python", theme="monokai", line_numbers=True)
        console.print(syntax)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument("node_id")
def metrics(node_id: str) -> None:
    """Show execution metrics for a node."""
    runtime = VesperRuntime()
    node_metrics = runtime.get_metrics(node_id)

    table = Table(title=f"Metrics for {node_id}")

    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Executions", str(node_metrics.total_executions))
    table.add_row("Python Executions", str(node_metrics.python_executions))
    table.add_row("Direct Executions", str(node_metrics.direct_executions))
    table.add_row("Errors", str(node_metrics.errors))
    table.add_row("Divergences", str(node_metrics.divergences))
    table.add_row("Avg Duration (ms)", f"{node_metrics.avg_duration_ms:.2f}")
    table.add_row("Error Rate", f"{node_metrics.error_rate:.2%}")
    table.add_row("Divergence Rate", f"{node_metrics.divergence_rate:.2%}")

    confidence = runtime.get_confidence(node_id)
    table.add_row("Confidence Score", f"{confidence:.4f}")

    console.print(table)


@main.command()
@click.argument("source", type=click.Path(exists=True, path_type=Path))
def test(source: Path) -> None:
    """Run test cases defined in a Vesper specification."""
    compiler = VesperCompiler()
    runtime = VesperRuntime()

    try:
        node = compiler.parse(source)
        runtime.load_node(source)

        console.print(f"[bold]Running tests for {node.node_id}[/bold]\n")

        if not node.testing.test_cases:
            console.print("[yellow]No test cases defined[/yellow]")
            return

        passed = 0
        failed = 0

        for test_case in node.testing.test_cases:
            result = runtime.execute_sync(node.node_id, test_case.inputs)

            # Simple check - in a real implementation, we'd compare properly
            if result.success:
                console.print(f"  [green]✓[/green] {test_case.name}")
                passed += 1
            else:
                console.print(f"  [red]✗[/red] {test_case.name}")
                console.print(f"    Error: {result.error}")
                failed += 1

        console.print()
        if failed == 0:
            console.print(f"[green]All {passed} tests passed![/green]")
        else:
            console.print(f"[yellow]{passed} passed, {failed} failed[/yellow]")
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
