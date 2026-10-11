`timescale 1ns/1ps

module fifo_read_adapter #(
    parameter integer WIDTH = 8
) (
    input logic clk,
    input logic rst_n,
    
    input logic fifo_empty,
    output logic fifo_rd_en,
    input logic fifo_rd_valid,
    input logic [WIDTH-1:0] fifo_rd_data,

    output logic out_valid,
    input logic out_ready,
    output logic [WIDTH-1:0] out_data
);

    logic read_pending;
    logic holding_valid;
    logic [WIDTH-1:0] holding_data;

    assign fifo_rd_en = rst_n && !fifo_empty && !read_pending && !holding_valid;
    assign out_valid = holding_valid;
    assign out_data = holding_data;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            read_pending <= 1'b0;
            holding_valid <= 1'b0;
            holding_data <= '0;
        end
        else begin
            if (fifo_rd_en) begin
                read_pending <= 1'b1;
            end
            else if (read_pending && fifo_rd_valid) begin
                holding_data <= fifo_rd_data;
                holding_valid <= 1'b1;
                read_pending <= 1'b0;
            end
            else if (holding_valid && out_ready) begin
                holding_valid <= 1'b0;
            end
        end
    end

endmodule