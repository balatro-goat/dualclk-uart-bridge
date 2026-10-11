`timescale 1ns/1ps

module tick_gen #(
    parameter integer DIV = 5
)(
    input logic clk,
    input logic rst_n,
    output logic tick
);

    localparam integer COUNT_WIDTH = (DIV <= 1) ? 1 : $clog2(DIV);
    localparam integer LAST_COUNT = DIV - 1;

    logic [COUNT_WIDTH-1:0] count;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count <= '0;
            tick <= 1'b0;
        end
        else if (DIV == 1) begin
            count <= '0;
            tick <= 1'b1;
        end
        else if (count == LAST_COUNT[COUNT_WIDTH-1:0]) begin
            count <= '0;
            tick <= 1'b1;
        end
        else begin
            count <= count + 1'b1;
            tick <= 1'b0;
        end
    end

endmodule