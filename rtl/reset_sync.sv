`timescale 1ns/1ps

module reset_sync (
    input logic clk,
    input logic rst_n_async,
    output logic rst_n_sync
);

    logic sync_ff1;

    always @(posedge clk or negedge rst_n_async) begin
        if (!rst_n_async) begin
            sync_ff1 <= 1'b0;
            rst_n_sync <= 1'b0;
        end
        else begin
            sync_ff1 <= 1'b1;
            rst_n_sync <= sync_ff1;
        end
    end

endmodule