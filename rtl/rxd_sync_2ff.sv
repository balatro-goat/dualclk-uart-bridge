`timescale 1ns/1ps

module rxd_sync_2ff(
    input logic clk,
    input logic rst_n,
    input logic rxd_async,
    output logic rxd_sync
);

    logic rxd_meta;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rxd_meta <= 1'b1;
            rxd_sync <= 1'b1;
        end
        else begin
            rxd_meta <= rxd_async;
            rxd_sync <= rxd_meta;
        end
    end

endmodule